"""
GFS ChunkServer 节点
- 存储实际数据块
- 向 Master 报告心跳
- 处理读写请求
- 副本同步
"""

import os
import json
import time
import hashlib
import threading
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class GFSChunkServer:
    """GFS ChunkServer - 数据存储节点"""

    def __init__(self, server_id: str, data_dir: str = "gfs_data",
                 master_url: str = "http://127.0.0.1:5000"):
        self.server_id = server_id
        self.data_dir = os.path.join(data_dir, "chunks", server_id)
        self.master_url = master_url
        os.makedirs(self.data_dir, exist_ok=True)

        # 本地 Chunk 存储
        self.chunks: Dict[str, dict] = {}  # chunk_id -> metadata

        # 统计信息
        self.stats = {
            "reads": 0,
            "writes": 0,
            "bytes_read": 0,
            "bytes_written": 0,
            "errors": 0
        }

        # 心跳线程
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        # 加载本地 Chunk 信息
        self._load_local_chunks()

        logger.info(f"ChunkServer {server_id} initialized at {self.data_dir}")

    def _load_local_chunks(self):
        """加载本地存储的 Chunk 信息"""
        metadata_file = os.path.join(self.data_dir, "chunks.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self.chunks = json.load(f)
                logger.info(f"Loaded {len(self.chunks)} local chunks")
            except Exception as e:
                logger.error(f"Failed to load chunk metadata: {e}")

    def _save_chunk_metadata(self):
        """保存 Chunk 元数据"""
        metadata_file = os.path.join(self.data_dir, "chunks.json")
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save chunk metadata: {e}")

    def _heartbeat_loop(self):
        """心跳上报循环"""
        import requests
        while self._running:
            try:
                url = f"{self.master_url}/api/gfs/heartbeat"
                requests.post(url, json={
                    "server_id": self.server_id,
                    "stats": self.stats,
                    "chunk_count": len(self.chunks)
                }, timeout=5)
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            time.sleep(10)

    def write_chunk(self, chunk_id: str, data: bytes) -> bool:
        """写入 Chunk 数据"""
        try:
            chunk_path = os.path.join(self.data_dir, f"{chunk_id}.dat")
            with open(chunk_path, 'wb') as f:
                f.write(data)

            # 计算校验和
            checksum = hashlib.md5(data).hexdigest()

            # 更新元数据
            self.chunks[chunk_id] = {
                "size": len(data),
                "checksum": checksum,
                "written_at": time.time()
            }
            self._save_chunk_metadata()

            self.stats["writes"] += 1
            self.stats["bytes_written"] += len(data)

            logger.info(f"Chunk {chunk_id} written: {len(data)} bytes")
            return True
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Failed to write chunk {chunk_id}: {e}")
            return False

    def read_chunk(self, chunk_id: str) -> Optional[bytes]:
        """读取 Chunk 数据"""
        try:
            chunk_path = os.path.join(self.data_dir, f"{chunk_id}.dat")
            if not os.path.exists(chunk_path):
                logger.warning(f"Chunk {chunk_id} not found")
                return None

            with open(chunk_path, 'rb') as f:
                data = f.read()

            # 验证校验和
            if chunk_id in self.chunks:
                expected = self.chunks[chunk_id].get("checksum", "")
                actual = hashlib.md5(data).hexdigest()
                if expected and expected != actual:
                    logger.error(f"Checksum mismatch for chunk {chunk_id}")
                    return None

            self.stats["reads"] += 1
            self.stats["bytes_read"] += len(data)

            return data
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Failed to read chunk {chunk_id}: {e}")
            return None

    def delete_chunk(self, chunk_id: str) -> bool:
        """删除 Chunk"""
        try:
            chunk_path = os.path.join(self.data_dir, f"{chunk_id}.dat")
            if os.path.exists(chunk_path):
                os.remove(chunk_path)

            self.chunks.pop(chunk_id, None)
            self._save_chunk_metadata()

            logger.info(f"Chunk {chunk_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id}: {e}")
            return False

    def get_stats(self) -> dict:
        """获取服务器统计"""
        total_size = sum(c.get("size", 0) for c in self.chunks.values())
        return {
            "server_id": self.server_id,
            "chunk_count": len(self.chunks),
            "total_size": total_size,
            **self.stats
        }

    def shutdown(self):
        """关闭服务器"""
        self._running = False
        logger.info(f"ChunkServer {self.server_id} shutdown")
