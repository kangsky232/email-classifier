"""
一致性哈希环实现
- 节点故障自动迁移到顺时针最近节点
- 虚拟节点保证负载均衡
- 数据自动恢复
"""

import hashlib
import bisect
import threading
import time
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConsistentHashRing:
    """一致性哈希环"""

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes  # 每个物理节点的虚拟节点数
        self.ring: Dict[int, str] = {}  # 哈希环: hash -> node_id
        self.sorted_keys: List[int] = []  # 排序后的哈希值
        self.physical_nodes: Dict[str, dict] = {}  # 物理节点信息
        self.lock = threading.RLock()
        self.failed_nodes: Set[str] = set()  # 故障节点集合
        self.node_load: Dict[str, int] = {}  # 节点负载统计

    def _hash(self, key: str) -> int:
        """计算哈希值"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node_id: str, node_info: dict = None):
        """添加节点到哈希环"""
        with self.lock:
            if node_id in self.physical_nodes:
                return

            self.physical_nodes[node_id] = node_info or {}
            self.node_load[node_id] = 0

            # 添加虚拟节点
            for i in range(self.virtual_nodes):
                virtual_key = f"{node_id}:vn{i}"
                hash_val = self._hash(virtual_key)
                self.ring[hash_val] = node_id
                bisect.insort(self.sorted_keys, hash_val)

            # 从故障列表中移除（如果存在）
            self.failed_nodes.discard(node_id)

            logger.info(f"Node {node_id} added to hash ring with {self.virtual_nodes} virtual nodes")

    def remove_node(self, node_id: str):
        """从哈希环移除节点"""
        with self.lock:
            if node_id not in self.physical_nodes:
                return

            # 移除虚拟节点
            for i in range(self.virtual_nodes):
                virtual_key = f"{node_id}:vn{i}"
                hash_val = self._hash(virtual_key)
                if hash_val in self.ring:
                    del self.ring[hash_val]
                    try:
                        self.sorted_keys.remove(hash_val)
                    except ValueError:
                        pass

            del self.physical_nodes[node_id]
            self.node_load.pop(node_id, None)

            logger.info(f"Node {node_id} removed from hash ring")

    def mark_failed(self, node_id: str):
        """标记节点故障"""
        with self.lock:
            if node_id in self.physical_nodes:
                self.failed_nodes.add(node_id)
                logger.warning(f"Node {node_id} marked as failed")

    def mark_recovered(self, node_id: str):
        """标记节点恢复"""
        with self.lock:
            self.failed_nodes.discard(node_id)
            logger.info(f"Node {node_id} marked as recovered")

    def get_node(self, key: str) -> Optional[str]:
        """根据 key 获取对应的节点（顺时针查找）"""
        with self.lock:
            if not self.sorted_keys:
                return None

            hash_val = self._hash(key)
            idx = bisect.bisect_right(self.sorted_keys, hash_val)

            # 顺时针查找，跳过故障节点
            start_idx = idx
            while True:
                if idx >= len(self.sorted_keys):
                    idx = 0

                node_id = self.ring[self.sorted_keys[idx]]

                # 如果节点正常，返回
                if node_id not in self.failed_nodes:
                    self.node_load[node_id] = self.node_load.get(node_id, 0) + 1
                    return node_id

                # 绕了一圈都是故障节点
                idx = (idx + 1) % len(self.sorted_keys)
                if idx == start_idx:
                    logger.error("All nodes are failed!")
                    return None

    def get_replica_nodes(self, key: str, replicas: int = 3) -> List[str]:
        """获取多个副本节点（用于数据冗余）"""
        with self.lock:
            if not self.sorted_keys:
                return []

            hash_val = self._hash(key)
            idx = bisect.bisect_right(self.sorted_keys, hash_val)

            result = []
            seen = set()

            while len(result) < replicas and len(seen) < len(self.physical_nodes):
                if idx >= len(self.sorted_keys):
                    idx = 0

                node_id = self.ring[self.sorted_keys[idx]]

                if node_id not in seen and node_id not in self.failed_nodes:
                    result.append(node_id)
                    seen.add(node_id)

                idx = (idx + 1) % len(self.sorted_keys)

            return result

    def get_migration_target(self, failed_node: str) -> List[str]:
        """获取故障节点数据的迁移目标"""
        with self.lock:
            # 获取所有正常节点
            healthy_nodes = [
                nid for nid in self.physical_nodes
                if nid not in self.failed_nodes and nid != failed_node
            ]

            if not healthy_nodes:
                return []

            # 按负载排序，优先迁移到负载低的节点
            healthy_nodes.sort(key=lambda n: self.node_load.get(n, 0))
            return healthy_nodes

    def get_all_nodes(self) -> List[dict]:
        """获取所有节点状态"""
        with self.lock:
            nodes = []
            for node_id, info in self.physical_nodes.items():
                nodes.append({
                    "id": node_id,
                    "failed": node_id in self.failed_nodes,
                    "load": self.node_load.get(node_id, 0),
                    **info
                })
            return nodes

    def get_ring_info(self) -> dict:
        """获取哈希环信息"""
        with self.lock:
            return {
                "total_nodes": len(self.physical_nodes),
                "failed_nodes": len(self.failed_nodes),
                "virtual_nodes": len(self.sorted_keys),
                "ring_size": len(self.sorted_keys)
            }


class ClusterManager:
    """集群管理器"""

    def __init__(self):
        self.hash_ring = ConsistentHashRing(virtual_nodes=100)
        self.node_health: Dict[str, dict] = {}  # 节点健康状态
        self.data_replicas: Dict[str, List[str]] = {}  # 数据副本映射
        self.lock = threading.Lock()
        self._health_check_thread = None
        self._running = False

    def register_node(self, node_id: str, node_info: dict):
        """注册节点"""
        self.hash_ring.add_node(node_id, node_info)
        self.node_health[node_id] = {
            "last_heartbeat": time.time(),
            "status": "online",
            "consecutive_failures": 0
        }

    def unregister_node(self, node_id: str):
        """注销节点"""
        self.hash_ring.remove_node(node_id)
        self.node_health.pop(node_id, None)

    def update_heartbeat(self, node_id: str):
        """更新节点心跳"""
        should_recover = False
        with self.lock:
            if node_id in self.node_health:
                self.node_health[node_id]["last_heartbeat"] = time.time()
                self.node_health[node_id]["status"] = "online"
                self.node_health[node_id]["consecutive_failures"] = 0

                if node_id in self.hash_ring.failed_nodes:
                    should_recover = True

        if should_recover:
            self.hash_ring.mark_recovered(node_id)
            self._on_node_recovered(node_id)

    def report_failure(self, node_id: str):
        """报告节点故障"""
        should_report = False
        with self.lock:
            if node_id in self.node_health:
                self.node_health[node_id]["consecutive_failures"] += 1

                # 连续3次失败才标记为故障
                if self.node_health[node_id]["consecutive_failures"] >= 3:
                    self.node_health[node_id]["status"] = "failed"
                    should_report = True

        if should_report:
            self.hash_ring.mark_failed(node_id)
            self._on_node_failed(node_id)

    def get_node_for_key(self, key: str) -> Optional[str]:
        """根据 key 获取目标节点"""
        return self.hash_ring.get_node(key)

    def get_replica_nodes(self, key: str, replicas: int = 3) -> List[str]:
        """获取副本节点"""
        return self.hash_ring.get_replica_nodes(key, replicas)

    def _on_node_failed(self, node_id: str):
        """节点故障处理"""
        logger.warning(f"Handling node failure: {node_id}")

        # 获取迁移目标
        targets = self.hash_ring.get_migration_target(node_id)

        # 收集需要迁移的数据 key（避免在锁内调用 hash_ring 方法）
        with self.lock:
            keys_to_migrate = [dk for dk, reps in self.data_replicas.items() if node_id in reps]

        for data_key in keys_to_migrate:
            new_replicas = self.hash_ring.get_replica_nodes(data_key)
            if new_replicas:
                with self.lock:
                    self.data_replicas[data_key] = new_replicas
                logger.info(f"Data {data_key} migrated from {node_id} to {new_replicas}")

    def _on_node_recovered(self, node_id: str):
        """节点恢复处理"""
        logger.info(f"Handling node recovery: {node_id}")

        # 收集需要恢复的数据 key（避免在锁内调用 hash_ring 方法）
        with self.lock:
            keys_to_check = list(self.data_replicas.keys())

        for data_key in keys_to_check:
            target_nodes = self.hash_ring.get_replica_nodes(data_key)
            if node_id in target_nodes:
                with self.lock:
                    replicas = self.data_replicas.get(data_key, [])
                    if node_id not in replicas:
                        replicas.append(node_id)
                        logger.info(f"Data {data_key} restored to recovered node {node_id}")

    def store_data(self, data_key: str) -> List[str]:
        """存储数据，返回副本位置"""
        replicas = self.hash_ring.get_replica_nodes(data_key, replicas=3)
        with self.lock:
            self.data_replicas[data_key] = replicas
        return replicas

    def get_cluster_status(self) -> dict:
        """获取集群状态"""
        with self.lock:
            nodes = self.hash_ring.get_all_nodes()
            ring_info = self.hash_ring.get_ring_info()

            return {
                "nodes": nodes,
                "ring": ring_info,
                "data_count": len(self.data_replicas),
                "healthy_count": sum(1 for n in nodes if not n["failed"]),
                "failed_count": sum(1 for n in nodes if n["failed"])
            }

    def start_health_check(self, check_interval: int = 10):
        """启动健康检查线程"""
        self._running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            args=(check_interval,),
            daemon=True
        )
        self._health_check_thread.start()
        logger.info(f"Health check started with interval {check_interval}s")

    def stop_health_check(self):
        """停止健康检查"""
        self._running = False
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)

    def _health_check_loop(self, interval: int):
        """健康检查循环"""
        while self._running:
            try:
                current_time = time.time()
                timeout = 30  # 30秒无心跳视为超时

                # Collect nodes that need failure reporting (avoid deadlock)
                failed_ids = []
                with self.lock:
                    for node_id, health in self.node_health.items():
                        if health["status"] == "online":
                            if current_time - health["last_heartbeat"] > timeout:
                                health["consecutive_failures"] += 1
                                if health["consecutive_failures"] >= 3:
                                    health["status"] = "failed"
                                    failed_ids.append(node_id)

                # Report failures outside the lock
                for node_id in failed_ids:
                    self.hash_ring.mark_failed(node_id)
                    self._on_node_failed(node_id)

                time.sleep(interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                time.sleep(interval)


# 全局集群管理器实例
cluster_manager = ClusterManager()
