from abc import ABC, abstractmethod
import time
import uuid

class BaseAgent(ABC):
    def __init__(self, name, method):
        self.id = f"agent-{uuid.uuid4().hex[:6]}"
        self.name = name
        self.method = method
        self.status = "online"
        self.processed_count = 0
        self.total_time = 0
        self.log = []
    
    @abstractmethod
    def classify(self, sender, subject, content):
        pass
    
    def _measure_time(self, func, *args):
        start = time.time()
        result = func(*args)
        elapsed = round((time.time() - start) * 1000, 2)
        self.total_time += elapsed
        self.processed_count += 1
        return result, elapsed
    
    def get_stats(self):
        avg_time = round(self.total_time / self.processed_count, 2) if self.processed_count > 0 else 0
        return {
            "id": self.id,
            "name": self.name,
            "method": self.method,
            "status": self.status,
            "processed_count": self.processed_count,
            "avg_time_ms": avg_time
        }
    
    def reset_stats(self):
        self.processed_count = 0
        self.total_time = 0
        self.log = []
