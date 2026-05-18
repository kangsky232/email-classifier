"""
分布式链路追踪
- Trace ID 传播
- Span 管理
- 请求链路可视化
"""

import uuid
import time
import threading
import logging
from typing import Dict, List, Optional
from collections import defaultdict, deque
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Span:
    """追踪 Span"""

    def __init__(self, trace_id: str, span_id: str, parent_id: Optional[str],
                 operation: str, service: str):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.operation = operation
        self.service = service
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None
        self.tags: Dict[str, str] = {}
        self.logs: List[dict] = []
        self.status = "OK"  # OK, ERROR

    def set_tag(self, key: str, value: str):
        """设置标签"""
        self.tags[key] = str(value)

    def log(self, message: str, **kwargs):
        """记录日志"""
        self.logs.append({
            "timestamp": time.time(),
            "message": message,
            **kwargs
        })

    def set_error(self, error: Exception):
        """标记错误"""
        self.status = "ERROR"
        self.tags["error"] = True
        self.tags["error.message"] = str(error)
        self.tags["error.type"] = type(error).__name__

    def finish(self):
        """结束 Span"""
        self.end_time = time.time()
        self.duration = (self.end_time - self.start_time) * 1000  # 毫秒

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "operation": self.operation,
            "service": self.service,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration,
            "tags": self.tags,
            "logs": self.logs,
            "status": self.status
        }


class Tracer:
    """分布式追踪器"""

    def __init__(self):
        self.traces: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.spans: Dict[str, Span] = {}
        self.lock = threading.RLock()
        self._current_span: Optional[Span] = None
        self._max_traces = 1000

    def start_trace(self, operation: str, service: str) -> Span:
        """开始新追踪"""
        trace_id = str(uuid.uuid4())[:16]
        span_id = str(uuid.uuid4())[:8]
        span = Span(trace_id, span_id, None, operation, service)

        with self.lock:
            self.traces[trace_id].append(span)
            self.spans[span_id] = span
            # 限制总 trace 数量，驱逐最旧的
            if len(self.traces) > self._max_traces:
                oldest_key = next(iter(self.traces))
                for s in self.traces.pop(oldest_key):
                    self.spans.pop(s.span_id, None)

        return span

    def start_span(self, operation: str, service: str, parent_span: Span = None) -> Span:
        """开始子 Span"""
        trace_id = parent_span.trace_id if parent_span else str(uuid.uuid4())[:16]
        span_id = str(uuid.uuid4())[:8]
        parent_id = parent_span.span_id if parent_span else None
        span = Span(trace_id, span_id, parent_id, operation, service)

        with self.lock:
            self.traces[trace_id].append(span)
            self.spans[span_id] = span

        return span

    @contextmanager
    def trace(self, operation: str, service: str):
        """追踪上下文管理器"""
        span = self.start_trace(operation, service)
        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            span.finish()

    def get_trace(self, trace_id: str) -> List[dict]:
        """获取追踪链路"""
        with self.lock:
            spans = self.traces.get(trace_id, [])
            return [s.to_dict() for s in spans]

    def get_recent_traces(self, limit: int = 100) -> List[dict]:
        """获取最近的追踪"""
        with self.lock:
            all_traces = []
            for trace_id, spans in self.traces.items():
                if spans:
                    root = spans[0]
                    all_traces.append({
                        "trace_id": trace_id,
                        "operation": root.operation,
                        "service": root.service,
                        "duration_ms": root.duration,
                        "span_count": len(spans),
                        "start_time": root.start_time,
                        "status": root.status
                    })
            all_traces.sort(key=lambda t: t["start_time"], reverse=True)
            return all_traces[:limit]

    def get_stats(self) -> dict:
        """获取追踪统计"""
        with self.lock:
            total_traces = len(self.traces)
            total_spans = len(self.spans)
            error_count = sum(1 for s in self.spans.values() if s.status == "ERROR")
            avg_duration = 0
            durations = [s.duration for s in self.spans.values() if s.duration]
            if durations:
                avg_duration = sum(durations) / len(durations)

            return {
                "total_traces": total_traces,
                "total_spans": total_spans,
                "error_count": error_count,
                "avg_duration_ms": round(avg_duration, 2)
            }


# 全局追踪器
tracer = Tracer()
