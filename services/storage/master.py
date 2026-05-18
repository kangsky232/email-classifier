"""
GFS Master 节点
- 文件命名空间管理
- Chunk 映射表 (文件ID → ChunkServer)
- 副本放置策略 (3副本，跨节点)
- 垃圾回收
"""

import os
import json
import time
import uuid
import threading
import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ChunkInfo:
    """Chunk 信息"""
    chunk_id: str
    file_id: str
    chunk_index: int  # 在文件中的索引
    size: int = 0
    checksum: str = ""
    servers: List[str] = field(default_factory=list)  # 存储该 Chunk 的服务器列表
    version: int = 1
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)


@dataclass
class FileInfo:
    """文件信息"""
    file_id: str
    file_path: str
    size: int = 0
    chunk_count: int = 0
    chunk_size: int = 4 * 1024 * 1024  # 4MB per chunk
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class GFSMaster:
    """GFS Master 节点"""

    def __init__(self, data_dir: str = "gfs_data"):
        self.data_dir = data_dir
        self.metadata_dir = os.path.join(data_dir, "master")
        os.makedirs(self.metadata_dir, exist_ok=True)

        # 元数据
        self.files: Dict[str, FileInfo] = {}  # file_id -> FileInfo
        self.chunks: Dict[str, ChunkInfo] = {}  # chunk_id -> ChunkInfo
        self.file_path_to_id: Dict[str, str] = {}  # file_path -> file_id

        # ChunkServer 管理
        self.chunk_servers: Dict[str, dict] = {}  # server_id -> server_info
        self.server_chunks: Dict[str, Set[str]] = defaultdict(set)  # server_id -> chunk_ids

        # 副本配置
        self.default_replicas = 3
        self.chunk_size = 4 * 1024 * 1024  # 4MB

        # 锁
        self.lock = threading.RLock()

        # 加载持久化数据
        self._load_metadata()

        logger.info(f"GFS Master initialized, data_dir={data_dir}")

    def _load_metadata(self):
        """加载持久化的元数据"""
        try:
            metadata_file = os.path.join(self.metadata_dir, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 恢复文件信息
                for fid, finfo in data.get("files", {}).items():
                    self.files[fid] = FileInfo(**finfo)
                    self.file_path_to_id[finfo["file_path"]] = fid

                # 恢复 Chunk 信息
                for cid, cinfo in data.get("chunks", {}).items():
                    self.chunks[cid] = ChunkInfo(**cinfo)

                logger.info(f"Loaded {len(self.files)} files, {len(self.chunks)} chunks")
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")

    def _save_metadata(self):
        """持久化元数据"""
        try:
            metadata_file = os.path.join(self.metadata_dir, "metadata.json")
            data = {
                "files": {fid: f.to_dict() for fid, f in self.files.items()},
                "chunks": {cid: c.to_dict() for cid, c in self.chunks.items()},
                "saved_at": time.time()
            }
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def register_chunk_server(self, server_id: str, server_info: dict):
        """注册 ChunkServer"""
        with self.lock:
            self.chunk_servers[server_id] = {
                **server_info,
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "status": "online"
            }
            logger.info(f"ChunkServer {server_id} registered")

    def unregister_chunk_server(self, server_id: str):
        """注销 ChunkServer"""
        with self.lock:
            if server_id in self.chunk_servers:
                del self.chunk_servers[server_id]

                # 处理该服务器上的 Chunk
                chunk_ids = self.server_chunks.pop(server_id, set())
                for chunk_id in chunk_ids:
                    if chunk_id in self.chunks:
                        self.chunks[chunk_id].servers.remove(server_id)

                logger.info(f"ChunkServer {server_id} unregistered")

    def update_server_heartbeat(self, server_id: str):
        """更新服务器心跳"""
        with self.lock:
            if server_id in self.chunk_servers:
                self.chunk_servers[server_id]["last_heartbeat"] = time.time()
                self.chunk_servers[server_id]["status"] = "online"

    def create_file(self, file_path: str, metadata: Dict = None) -> str:
        """创建文件，返回 file_id"""
        with self.lock:
            # 检查是否已存在
            if file_path in self.file_path_to_id:
                return self.file_path_to_id[file_path]

            file_id = str(uuid.uuid4())[:12]
            file_info = FileInfo(
                file_id=file_id,
                file_path=file_path,
                metadata=metadata or {}
            )

            self.files[file_id] = file_info
            self.file_path_to_id[file_path] = file_id

            self._save_metadata()
            logger.info(f"File created: {file_path} -> {file_id}")

            return file_id

    def allocate_chunk(self, file_id: str, chunk_index: int) -> Optional[ChunkInfo]:
        """为文件分配 Chunk"""
        with self.lock:
            if file_id not in self.files:
                logger.error(f"File {file_id} not found")
                return None

            # 选择存储服务器
            servers = self._select_servers(self.default_replicas)
            if not servers:
                logger.error("No available ChunkServer")
                return None

            chunk_id = f"{file_id}_chunk_{chunk_index}"
            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                file_id=file_id,
                chunk_index=chunk_index,
                servers=servers
            )

            self.chunks[chunk_id] = chunk_info

            # 更新服务器 Chunk 映射
            for server_id in servers:
                self.server_chunks[server_id].add(chunk_id)

            # 更新文件信息
            file_info = self.files[file_id]
            file_info.chunk_count = max(file_info.chunk_count, chunk_index + 1)

            self._save_metadata()
            logger.info(f"Chunk allocated: {chunk_id} -> {servers}")

            return chunk_info

    def get_file_chunks(self, file_id: str) -> List[ChunkInfo]:
        """获取文件的所有 Chunk"""
        with self.lock:
            if file_id not in self.files:
                return []

            chunks = [
                chunk for chunk in self.chunks.values()
                if chunk.file_id == file_id
            ]
            chunks.sort(key=lambda c: c.chunk_index)
            return chunks

    def get_chunk_servers(self, chunk_id: str) -> List[str]:
        """获取 Chunk 存储的服务器列表"""
        with self.lock:
            if chunk_id not in self.chunks:
                return []
            return list(self.chunks[chunk_id].servers)

    def _select_servers(self, count: int) -> List[str]:
        """选择存储服务器（负载均衡）"""
        available_servers = [
            sid for sid, info in self.chunk_servers.items()
            if info.get("status") == "online"
        ]

        if len(available_servers) < count:
            logger.warning(f"Not enough servers: need {count}, have {len(available_servers)}")
            return available_servers

        # 按负载排序，选择负载最低的服务器
        server_loads = []
        for sid in available_servers:
            load = len(self.server_chunks.get(sid, set()))
            server_loads.append((sid, load))

        server_loads.sort(key=lambda x: x[1])
        return [sid for sid, _ in server_loads[:count]]

    def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        with self.lock:
            if file_id not in self.files:
                return False

            file_info = self.files[file_id]

            # 删除所有 Chunk
            chunk_ids = [cid for cid, c in self.chunks.items() if c.file_id == file_id]
            for chunk_id in chunk_ids:
                chunk = self.chunks.pop(chunk_id)
                for server_id in chunk.servers:
                    self.server_chunks[server_id].discard(chunk_id)

            # 删除文件记录
            del self.files[file_id]
            if file_info.file_path in self.file_path_to_id:
                del self.file_path_to_id[file_info.file_path]

            self._save_metadata()
            logger.info(f"File deleted: {file_id}")
            return True

    def get_file_info(self, file_id: str) -> Optional[FileInfo]:
        """获取文件信息"""
        with self.lock:
            return self.files.get(file_id)

    def list_files(self) -> List[FileInfo]:
        """列出所有文件"""
        with self.lock:
            return list(self.files.values())

    def get_cluster_info(self) -> dict:
        """获取集群信息"""
        with self.lock:
            return {
                "total_files": len(self.files),
                "total_chunks": len(self.chunks),
                "total_servers": len(self.chunk_servers),
                "online_servers": sum(
                    1 for s in self.chunk_servers.values()
                    if s.get("status") == "online"
                ),
                "total_size": sum(f.size for f in self.files.values()),
                "replication_factor": self.default_replicas
            }

    def rebalance_replicas(self):
        """重新平衡副本"""
        with self.lock:
            for chunk_id, chunk in self.chunks.items():
                # 检查副本数量
                active_servers = [
                    s for s in chunk.servers
                    if s in self.chunk_servers and self.chunk_servers[s].get("status") == "online"
                ]

                if len(active_servers) < self.default_replicas:
                    # 需要添加副本
                    needed = self.default_replicas - len(active_servers)
                    new_servers = self._select_servers(needed + len(active_servers))
                    new_servers = [s for s in new_servers if s not in active_servers]

                    for server_id in new_servers[:needed]:
                        chunk.servers.append(server_id)
                        self.server_chunks[server_id].add(chunk_id)
                        logger.info(f"Added replica for {chunk_id} on {server_id}")

            self._save_metadata()


# 全局 GFS Master 实例
gfs_master = GFSMaster()
