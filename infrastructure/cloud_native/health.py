"""
健康检查
- Kubernetes 风格探针
- 就绪探针 (Readiness)
- 存活探针 (Liveness)
- 启动探针 (Startup)
"""

import time
import threading
import logging
from typing import Dict, List, Callable, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    UP = "UP"
    DOWN = "DOWN"
    STARTING = "STARTING"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class ProbeType(Enum):
    """探针类型"""
    LIVENESS = "liveness"  # 存活探针
    READINESS = "readiness"  # 就绪探针
    STARTUP = "startup"  # 启动探针


class HealthCheck:
    """健康检查项"""

    def __init__(self, name: str, check_func: Callable, probe_type: ProbeType = ProbeType.LIVENESS):
        self.name = name
        self.check_func = check_func
        self.probe_type = probe_type
        self.status = HealthStatus.STARTING
        self.last_check_time = 0
        self.last_error: Optional[str] = None
        self.consecutive_failures = 0

    def check(self) -> HealthStatus:
        """执行检查"""
        try:
            result = self.check_func()
            self.status = HealthStatus.UP if result else HealthStatus.DOWN
            self.consecutive_failures = 0
            self.last_error = None
        except Exception as e:
            self.status = HealthStatus.DOWN
            self.consecutive_failures += 1
            self.last_error = str(e)
            logger.warning(f"Health check {self.name} failed: {e}")

        self.last_check_time = time.time()
        return self.status

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "probe_type": self.probe_type.value,
            "last_check_time": self.last_check_time,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error
        }


class HealthChecker:
    """健康检查管理器"""

    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.lock = threading.RLock()
        self._check_thread = None
        self._running = False
        self._started_at = time.time()

    def register(self, name: str, check_func: Callable,
                 probe_type: ProbeType = ProbeType.LIVENESS):
        """注册健康检查"""
        with self.lock:
            self.checks[name] = HealthCheck(name, check_func, probe_type)
            logger.info(f"Health check registered: {name}")

    def check_all(self) -> dict:
        """执行所有检查"""
        with self.lock:
            results = {}
            overall_status = HealthStatus.UP

            for name, check in self.checks.items():
                status = check.check()
                results[name] = check.to_dict()

                if status != HealthStatus.UP:
                    if check.probe_type == ProbeType.LIVENESS:
                        overall_status = HealthStatus.DOWN

            return {
                "status": overall_status.value,
                "timestamp": time.time(),
                "uptime_seconds": round(time.time() - self._started_at, 2),
                "checks": results
            }

    def check_probe(self, probe_type: ProbeType) -> dict:
        """检查指定类型的探针"""
        with self.lock:
            results = {}
            overall_status = HealthStatus.UP

            for name, check in self.checks.items():
                if check.probe_type == probe_type:
                    status = check.check()
                    results[name] = check.to_dict()

                    if status != HealthStatus.UP:
                        overall_status = HealthStatus.DOWN

            return {
                "status": overall_status.value,
                "probe_type": probe_type.value,
                "timestamp": time.time(),
                "checks": results
            }

    def liveness(self) -> dict:
        """存活探针"""
        return self.check_probe(ProbeType.LIVENESS)

    def readiness(self) -> dict:
        """就绪探针"""
        return self.check_probe(ProbeType.READINESS)

    def startup(self) -> dict:
        """启动探针"""
        return self.check_probe(ProbeType.STARTUP)

    def start(self, interval: int = 30):
        """启动定时检查"""
        self._running = True
        self._check_thread = threading.Thread(
            target=self._check_loop,
            args=(interval,),
            daemon=True
        )
        self._check_thread.start()
        logger.info(f"Health checker started with interval {interval}s")

    def _check_loop(self, interval: int):
        """检查循环"""
        while self._running:
            try:
                self.check_all()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
            time.sleep(interval)

    def stop(self):
        """停止检查"""
        self._running = False


# 全局健康检查器
health_checker = HealthChecker()
