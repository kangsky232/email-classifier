"""
智能负载均衡器
- 加权轮询
- 最少连接
- 响应时间感知
- 健康检查感知
"""

import time
import threading
import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class LoadBalancer:
    """智能负载均衡器"""

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.lock = threading.RLock()

        # 统计数据
        self.stats = defaultdict(lambda: {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "total_response_time": 0,
            "avg_response_time": 0,
            "last_request_time": 0,
            "active_connections": 0
        })

    def register_node(self, node_id: str, weight: int = 1):
        """注册节点"""
        with self.lock:
            self.nodes[node_id] = {
                "weight": weight,
                "status": "online",
                "registered_at": time.time()
            }
            logger.info(f"Load balancer: node {node_id} registered with weight {weight}")

    def unregister_node(self, node_id: str):
        """注销节点"""
        with self.lock:
            self.nodes.pop(node_id, None)
            self.stats.pop(node_id, None)

    def mark_failed(self, node_id: str):
        """标记节点故障"""
        with self.lock:
            if node_id in self.nodes:
                self.nodes[node_id]["status"] = "failed"

    def mark_recovered(self, node_id: str):
        """标记节点恢复"""
        with self.lock:
            if node_id in self.nodes:
                self.nodes[node_id]["status"] = "online"

    def get_node_weighted_round_robin(self) -> Optional[str]:
        """加权轮询选择"""
        with self.lock:
            online_nodes = [
                (nid, info) for nid, info in self.nodes.items()
                if info["status"] == "online"
            ]

            if not online_nodes:
                return None

            # 计算加权分数
            best_node = None
            best_score = -1

            for node_id, info in online_nodes:
                weight = info.get("weight", 1)
                stat = self.stats[node_id]
                requests = stat["requests"]

                # 加权分数 = 权重 / (请求数 + 1)
                score = weight / (requests + 1)

                if score > best_score:
                    best_score = score
                    best_node = node_id

            return best_node

    def get_node_least_connections(self) -> Optional[str]:
        """最少连接选择"""
        with self.lock:
            online_nodes = [
                nid for nid, info in self.nodes.items()
                if info["status"] == "online"
            ]

            if not online_nodes:
                return None

            return min(online_nodes, key=lambda n: self.stats[n]["active_connections"])

    def get_node_fastest_response(self) -> Optional[str]:
        """最快响应选择"""
        with self.lock:
            online_nodes = [
                nid for nid, info in self.nodes.items()
                if info["status"] == "online"
            ]

            if not online_nodes:
                return None

            # 优先选择有历史数据且响应快的节点
            def get_avg_time(node_id):
                stat = self.stats[node_id]
                if stat["requests"] == 0:
                    return 0  # 无历史数据，优先选择
                return stat["avg_response_time"]

            return min(online_nodes, key=get_avg_time)

    def get_node_health_aware(self) -> Optional[str]:
        """健康感知选择 - 综合考虑多种因素"""
        with self.lock:
            online_nodes = [
                (nid, info) for nid, info in self.nodes.items()
                if info["status"] == "online"
            ]

            if not online_nodes:
                return None

            def calculate_score(node_id, info):
                weight = info.get("weight", 1)
                stat = self.stats[node_id]

                # 基础分数（权重）
                score = weight * 100

                # 连接数惩罚
                connections = stat["active_connections"]
                score -= connections * 10

                # 响应时间惩罚
                if stat["requests"] > 0:
                    avg_time = stat["avg_response_time"]
                    if avg_time > 1000:  # 超过1秒
                        score -= 50
                    elif avg_time > 500:  # 超过500ms
                        score -= 20

                # 失败率惩罚
                if stat["requests"] > 0:
                    fail_rate = stat["failures"] / stat["requests"]
                    if fail_rate > 0.1:  # 失败率超过10%
                        score -= 100
                    elif fail_rate > 0.05:  # 失败率超过5%
                        score -= 50

                return score

            best_node = max(
                online_nodes,
                key=lambda x: calculate_score(x[0], x[1])
            )
            return best_node[0]

    def select_node(self, strategy: str = "health_aware") -> Optional[str]:
        """根据策略选择节点"""
        strategies = {
            "weighted_round_robin": self.get_node_weighted_round_robin,
            "least_connections": self.get_node_least_connections,
            "fastest_response": self.get_node_fastest_response,
            "health_aware": self.get_node_health_aware
        }

        select_func = strategies.get(strategy, self.get_node_health_aware)
        node_id = select_func()

        if node_id:
            with self.lock:
                self.stats[node_id]["active_connections"] += 1

        return node_id

    def record_request(self, node_id: str, response_time: float, success: bool):
        """记录请求结果"""
        with self.lock:
            if node_id not in self.stats:
                return

            stat = self.stats[node_id]
            stat["requests"] += 1
            stat["last_request_time"] = time.time()
            stat["active_connections"] = max(0, stat["active_connections"] - 1)

            if success:
                stat["successes"] += 1
            else:
                stat["failures"] += 1

            # 更新平均响应时间
            stat["total_response_time"] += response_time
            stat["avg_response_time"] = stat["total_response_time"] / stat["requests"]

    def get_stats(self) -> dict:
        """获取负载均衡统计"""
        with self.lock:
            return {
                "nodes": {
                    nid: {
                        "info": info,
                        "stats": dict(self.stats[nid])
                    }
                    for nid, info in self.nodes.items()
                },
                "total_nodes": len(self.nodes),
                "online_nodes": sum(1 for n in self.nodes.values() if n["status"] == "online"),
                "total_requests": sum(s["requests"] for s in self.stats.values())
            }


# 全局负载均衡器实例
load_balancer = LoadBalancer()
