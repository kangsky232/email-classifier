"""
服务注册与发现
- 服务自动注册
- 心跳检测
- 服务发现
- 负载均衡
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class ServiceInstance:
    """服务实例"""

    def __init__(self, service_id: str, service_name: str, host: str, port: int,
                 metadata: dict = None):
        self.service_id = service_id
        self.service_name = service_name
        self.host = host
        self.port = port
        self.metadata = metadata or {}
        self.registered_at = time.time()
        self.last_heartbeat = time.time()
        self.status = "UP"  # UP, DOWN, STARTING, OUT_OF_SERVICE
        self.weight = 1

    def to_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "metadata": self.metadata,
            "status": self.status,
            "weight": self.weight,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "url": f"http://{self.host}:{self.port}"
        }


class ServiceRegistry:
    """服务注册中心"""

    def __init__(self):
        self.services: Dict[str, Dict[str, ServiceInstance]] = defaultdict(dict)
        self.lock = threading.RLock()
        self._health_check_thread = None
        self._running = False
        self.heartbeat_timeout = 30  # 30秒无心跳视为下线

    def register(self, service_id: str, service_name: str, host: str, port: int,
                 metadata: dict = None) -> ServiceInstance:
        """注册服务"""
        with self.lock:
            instance = ServiceInstance(service_id, service_name, host, port, metadata)
            self.services[service_name][service_id] = instance
            logger.info(f"Service registered: {service_name}/{service_id} at {host}:{port}")
            return instance

    def deregister(self, service_name: str, service_id: str):
        """注销服务"""
        with self.lock:
            if service_name in self.services:
                self.services[service_name].pop(service_id, None)
                logger.info(f"Service deregistered: {service_name}/{service_id}")

    def heartbeat(self, service_name: str, service_id: str):
        """更新心跳"""
        with self.lock:
            if service_name in self.services and service_id in self.services[service_name]:
                instance = self.services[service_name][service_id]
                instance.last_heartbeat = time.time()
                instance.status = "UP"

    def get_service(self, service_name: str) -> List[ServiceInstance]:
        """获取服务实例列表"""
        with self.lock:
            instances = list(self.services.get(service_name, {}).values())
            return [i for i in instances if i.status == "UP"]

    def get_all_services(self) -> Dict[str, List[dict]]:
        """获取所有服务"""
        with self.lock:
            result = {}
            for name, instances in self.services.items():
                result[name] = [i.to_dict() for i in instances.values()]
            return result

    def get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务 URL（负载均衡）"""
        instances = self.get_service(service_name)
        if not instances:
            return None
        # 简单轮询
        instance = min(instances, key=lambda i: i.weight)
        return f"http://{instance.host}:{instance.port}"

    def start_health_check(self, interval: int = 10):
        """启动健康检查"""
        self._running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            args=(interval,),
            daemon=True
        )
        self._health_check_thread.start()
        logger.info(f"Service registry health check started with interval {interval}s")

    def _health_check_loop(self, interval: int):
        """健康检查循环"""
        while self._running:
            try:
                current_time = time.time()
                with self.lock:
                    for name, instances in self.services.items():
                        for sid, instance in list(instances.items()):
                            if current_time - instance.last_heartbeat > self.heartbeat_timeout:
                                instance.status = "DOWN"
                                logger.warning(f"Service {name}/{sid} marked as DOWN")
            except Exception as e:
                logger.error(f"Health check error: {e}")
            time.sleep(interval)

    def stop(self):
        """停止健康检查"""
        self._running = False


# 全局服务注册中心
service_registry = ServiceRegistry()
