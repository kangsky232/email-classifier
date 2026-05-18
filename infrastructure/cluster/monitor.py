"""
集群监控模块
- 节点状态监控
- 资源使用统计
- 负载均衡信息
- Paxos 共识统计
"""

import time
import threading
import logging
import psutil
import requests
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class ClusterMonitor:
    """集群监控器"""

    def __init__(self):
        self.node_metrics: Dict[str, dict] = {}  # 节点指标
        self.cluster_metrics: dict = {  # 集群级指标
            "total_requests": 0,
            "total_classifications": 0,
            "paxos_consensus_count": 0,
            "paxos_success_count": 0,
            "avg_response_time": 0,
            "response_times": deque(maxlen=1000)
        }
        self.metric_history: Dict[str, deque] = {}  # 历史指标
        self.lock = threading.RLock()
        self._collection_thread = None
        self._running = False

        # 初始化本机指标
        self.local_metrics = {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_mb": 0,
            "disk_percent": 0,
            "network_bytes_sent": 0,
            "network_bytes_recv": 0,
            "process_count": 0
        }

    def start(self, collection_interval: int = 5):
        """启动指标采集"""
        self._running = True
        self._collection_thread = threading.Thread(
            target=self._collection_loop,
            args=(collection_interval,),
            daemon=True
        )
        self._collection_thread.start()
        logger.info(f"Cluster monitor started with interval {collection_interval}s")

    def stop(self):
        """停止指标采集"""
        self._running = False
        if self._collection_thread:
            self._collection_thread.join(timeout=5)

    def _collection_loop(self, interval: int):
        """指标采集循环"""
        while self._running:
            try:
                self._collect_local_metrics()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Metric collection error: {e}")
                time.sleep(interval)

    def _collect_local_metrics(self):
        """采集本机指标"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            # Windows 兼容：使用当前工作目录所在磁盘
            import os
            disk_path = os.path.splitdrive(os.getcwd())[0] + '\\' if os.name == 'nt' else '/'
            disk = psutil.disk_usage(disk_path)
            net = psutil.net_io_counters()

            with self.lock:
                self.local_metrics.update({
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_mb": round(memory.used / 1024 / 1024, 1),
                    "memory_total_mb": round(memory.total / 1024 / 1024, 1),
                    "disk_percent": disk.percent,
                    "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                    "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                    "network_bytes_sent": net.bytes_sent,
                    "network_bytes_recv": net.bytes_recv,
                    "process_count": len(psutil.pids()),
                    "timestamp": time.time()
                })

                # 记录历史
                for key in ["cpu_percent", "memory_percent"]:
                    if key not in self.metric_history:
                        self.metric_history[key] = deque(maxlen=360)  # 1小时历史
                    self.metric_history[key].append({
                        "value": self.local_metrics[key],
                        "timestamp": time.time()
                    })

        except Exception as e:
            logger.error(f"Failed to collect local metrics: {e}")

    def update_node_metrics(self, node_id: str, metrics: dict):
        """更新节点指标"""
        with self.lock:
            self.node_metrics[node_id] = {
                **metrics,
                "last_update": time.time()
            }

    def record_request(self, response_time_ms: float):
        """记录请求"""
        with self.lock:
            self.cluster_metrics["total_requests"] += 1
            self.cluster_metrics["response_times"].append(response_time_ms)

            # 计算平均响应时间
            times = self.cluster_metrics["response_times"]
            if times:
                self.cluster_metrics["avg_response_time"] = round(
                    sum(times) / len(times), 2
                )

    def record_classification(self, success: bool = True):
        """记录分类"""
        with self.lock:
            self.cluster_metrics["total_classifications"] += 1

    def record_paxos_consensus(self, success: bool):
        """记录 Paxos 共识"""
        with self.lock:
            self.cluster_metrics["paxos_consensus_count"] += 1
            if success:
                self.cluster_metrics["paxos_success_count"] += 1

    def get_node_metrics(self, node_id: str) -> Optional[dict]:
        """获取节点指标"""
        with self.lock:
            return self.node_metrics.get(node_id)

    def get_all_node_metrics(self) -> Dict[str, dict]:
        """获取所有节点指标"""
        with self.lock:
            return dict(self.node_metrics)

    def get_local_metrics(self) -> dict:
        """获取本机指标"""
        with self.lock:
            return dict(self.local_metrics)

    def get_cluster_metrics(self) -> dict:
        """获取集群指标"""
        with self.lock:
            paxos_total = self.cluster_metrics["paxos_consensus_count"]
            paxos_success = self.cluster_metrics["paxos_success_count"]
            paxos_rate = round(paxos_success / paxos_total * 100, 1) if paxos_total > 0 else 100

            return {
                "total_requests": self.cluster_metrics["total_requests"],
                "total_classifications": self.cluster_metrics["total_classifications"],
                "paxos_consensus_count": paxos_total,
                "paxos_success_count": paxos_success,
                "paxos_success_rate": paxos_rate,
                "avg_response_time": self.cluster_metrics["avg_response_time"]
            }

    def get_metric_history(self, metric: str, limit: int = 60) -> List[dict]:
        """获取指标历史"""
        with self.lock:
            history = self.metric_history.get(metric, deque())
            return list(history)[-limit:]

    def fetch_remote_node_metrics(self, nodes: List[dict]):
        """采集远程节点指标"""
        for node in nodes:
            try:
                url = node.get("url", "")
                if not url:
                    continue

                resp = requests.get(f"{url}/stats", timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    self.update_node_metrics(node["id"], {
                        "name": node.get("name", node["id"]),
                        "status": "online",
                        "request_count": data.get("request_count", 0),
                        "uptime_seconds": data.get("uptime_seconds", 0),
                        "agent_stats": data.get("agent", {}),
                        "acceptor_log": data.get("acceptor_log", [])
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch metrics from {node.get('id')}: {e}")
                self.update_node_metrics(node["id"], {
                    "name": node.get("name", node["id"]),
                    "status": "offline",
                    "error": str(e)
                })


# 全局监控器实例
cluster_monitor = ClusterMonitor()
