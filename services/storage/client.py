"""
GFS Client
- 文件分片上传/下载
- 自动选择最近副本
- 透明故障切换
"""

import os
import hashlib
import logging
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)


class GFSClient:
    """GFS 客户端 - 提供文件级 API"""

    def __init__(self, master_url: str = "http://127.0.0.1:5000"):
        self.master_url = master_url
        self.chunk_size = 4 * 1024 * 1024  # 4MB

    def upload_file(self, file_path: str, data: bytes,
                    metadata: dict = None) -> Optional[str]:
        """上传文件到 GFS"""
        try:
            # 1. 在 Master 创建文件
            resp = requests.post(f"{self.master_url}/api/gfs/files", json={
                "file_path": file_path,
                "metadata": metadata or {}
            }, timeout=10)
            resp.raise_for_status()
            file_info = resp.json()
            file_id = file_info["file_id"]

            # 2. 分片上传
            total_size = len(data)
            chunk_count = (total_size + self.chunk_size - 1) // self.chunk_size

            for i in range(chunk_count):
                start = i * self.chunk_size
                end = min(start + self.chunk_size, total_size)
                chunk_data = data[start:end]

                # 2a. 分配 Chunk
                resp = requests.post(f"{self.master_url}/api/gfs/chunks/allocate", json={
                    "file_id": file_id,
                    "chunk_index": i
                }, timeout=10)
                resp.raise_for_status()
                chunk_info = resp.json()

                # 2b. 写入到每个副本服务器
                chunk_id = chunk_info["chunk_id"]
                servers = chunk_info["servers"]

                success_count = 0
                for server_id in servers:
                    if self._write_to_server(server_id, chunk_id, chunk_data):
                        success_count += 1

                if success_count == 0:
                    logger.error(f"All replicas failed for chunk {chunk_id}")
                    return None

            # 3. 更新文件大小
            requests.put(f"{self.master_url}/api/gfs/files/{file_id}", json={
                "size": total_size,
                "chunk_count": chunk_count
            }, timeout=10)

            logger.info(f"File uploaded: {file_path} -> {file_id} ({total_size} bytes)")
            return file_id

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None

    def download_file(self, file_id: str) -> Optional[bytes]:
        """从 GFS 下载文件"""
        try:
            # 1. 获取文件 Chunk 列表
            resp = requests.get(f"{self.master_url}/api/gfs/files/{file_id}/chunks", timeout=10)
            resp.raise_for_status()
            chunks = resp.json()

            if not chunks:
                logger.warning(f"No chunks found for file {file_id}")
                return None

            # 2. 按顺序下载并拼接
            chunks.sort(key=lambda c: c["chunk_index"])
            file_data = bytearray()

            for chunk in chunks:
                chunk_id = chunk["chunk_id"]
                servers = chunk["servers"]

                # 尝试从任一副本读取
                chunk_data = None
                for server_id in servers:
                    chunk_data = self._read_from_server(server_id, chunk_id)
                    if chunk_data:
                        break

                if chunk_data is None:
                    logger.error(f"All replicas failed for chunk {chunk_id}")
                    return None

                file_data.extend(chunk_data)

            logger.info(f"File downloaded: {file_id} ({len(file_data)} bytes)")
            return bytes(file_data)

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def _write_to_server(self, server_id: str, chunk_id: str, data: bytes) -> bool:
        """写入数据到指定服务器"""
        try:
            resp = requests.post(
                f"{self.master_url}/api/gfs/chunks/write",
                json={
                    "server_id": server_id,
                    "chunk_id": chunk_id,
                    "data": data.hex()
                },
                timeout=30
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Write to {server_id} failed: {e}")
            return False

    def _read_from_server(self, server_id: str, chunk_id: str) -> Optional[bytes]:
        """从指定服务器读取数据"""
        try:
            resp = requests.get(
                f"{self.master_url}/api/gfs/chunks/read",
                params={"server_id": server_id, "chunk_id": chunk_id},
                timeout=30
            )
            if resp.status_code == 200:
                return bytes.fromhex(resp.json()["data"])
            return None
        except Exception as e:
            logger.warning(f"Read from {server_id} failed: {e}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """删除文件"""
        try:
            resp = requests.delete(f"{self.master_url}/api/gfs/files/{file_id}", timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
