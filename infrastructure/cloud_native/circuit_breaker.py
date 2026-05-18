"""
熔断降级
- 失败率熔断
- 慢调用熔断
- 半开状态
- 降级处理
"""

import time
import threading
import logging
from typing import Callable, Optional
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常状态，允许请求
    OPEN = "open"  # 熔断状态，拒绝请求
    HALF_OPEN = "half_open"  # 半开状态，允许探测请求


class CircuitBreaker:
    """熔断器"""

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: int = 30, slow_call_threshold: float = 1000,
                 slow_call_rate_threshold: float = 0.5):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.slow_call_threshold = slow_call_threshold  # 毫秒
        self.slow_call_rate_threshold = slow_call_rate_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.slow_call_count = 0
        self.total_calls = 0
        self.last_failure_time = 0
        self.last_state_change = time.time()

        # 最近调用记录
        self.recent_calls = deque(maxlen=100)

        self.lock = threading.RLock()
        self._fallback: Optional[Callable] = None

    def set_fallback(self, fallback: Callable):
        """设置降级函数"""
        self._fallback = fallback

    def call(self, func: Callable, *args, **kwargs):
        """执行调用"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    return self._handle_fallback("Circuit is OPEN")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000

            with self.lock:
                self._record_success(duration)

            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000

            with self.lock:
                self._record_failure(duration)

            raise

    def _record_success(self, duration: float):
        """记录成功调用"""
        self.total_calls += 1
        self.success_count += 1

        is_slow = duration > self.slow_call_threshold
        if is_slow:
            self.slow_call_count += 1

        self.recent_calls.append({
            "success": True,
            "duration": duration,
            "slow": is_slow,
            "timestamp": time.time()
        })

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, duration: float):
        """记录失败调用"""
        self.total_calls += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        self.recent_calls.append({
            "success": False,
            "duration": duration,
            "slow": False,
            "timestamp": time.time()
        })

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.slow_call_count = 0

        logger.info(f"Circuit {self.name}: {old_state.value} -> {new_state.value}")

    def _handle_fallback(self, reason: str):
        """处理降级"""
        if self._fallback:
            return self._fallback(reason)
        raise Exception(f"Circuit {self.name} is OPEN: {reason}")

    def get_stats(self) -> dict:
        """获取统计"""
        with self.lock:
            failure_rate = self.failure_count / self.total_calls if self.total_calls > 0 else 0
            slow_rate = self.slow_call_count / self.total_calls if self.total_calls > 0 else 0

            return {
                "name": self.name,
                "state": self.state.value,
                "total_calls": self.total_calls,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "slow_call_count": self.slow_call_count,
                "failure_rate": round(failure_rate, 4),
                "slow_call_rate": round(slow_rate, 4),
                "last_failure_time": self.last_failure_time,
                "last_state_change": self.last_state_change
            }

    def reset(self):
        """重置熔断器"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.slow_call_count = 0
            self.total_calls = 0
            self.recent_calls.clear()


# 熔断器管理
class CircuitBreakerManager:
    """熔断器管理器"""

    def __init__(self):
        self.breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(self, name: str, **kwargs) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, **kwargs)
        return self.breakers[name]

    def get_all_stats(self) -> dict:
        """获取所有熔断器统计"""
        return {
            name: breaker.get_stats()
            for name, breaker in self.breakers.items()
        }


# 全局熔断器管理器
circuit_breaker = CircuitBreakerManager()
