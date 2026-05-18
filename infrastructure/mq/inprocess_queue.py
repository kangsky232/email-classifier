import threading
import queue
import time
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class InProcessMQ:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._queues = {
            'email_input': queue.Queue(),
            'classification_result': queue.Queue(),
            'paxos_proposal': queue.Queue(),
            'final_action': queue.Queue(),
        }
        self._handlers = {}
        self._message_log = deque(maxlen=50)
        self._stats = defaultdict(int)
        self._consuming = False

    def publish(self, queue_name, message):
        if queue_name not in self._queues:
            return False
        msg = {
            'queue': queue_name,
            'body': message,
            'timestamp': time.time()
        }
        self._queues[queue_name].put(msg)
        self._stats[queue_name] += 1
        self._message_log.appendleft(msg)
        logger.info(f"Published to [{queue_name}]: {message.get('type', 'unknown')}")
        return True

    def subscribe(self, queue_name, handler):
        if queue_name not in self._queues:
            return False
        self._handlers[queue_name] = handler
        logger.info(f"Handler registered for [{queue_name}]")
        return True

    def start_consuming(self):
        if self._consuming:
            return
        self._consuming = True
        for q_name, q in self._queues.items():
            t = threading.Thread(target=self._consume_loop, args=(q_name, q), daemon=True)
            t.start()
        logger.info("In-process MQ consumers started")

    def _consume_loop(self, queue_name, q):
        while True:
            try:
                msg = q.get(timeout=2)
                handler = self._handlers.get(queue_name)
                if handler:
                    try:
                        handler(msg['body'])
                    except Exception as e:
                        logger.error(f"InProcessMQ handler error [{queue_name}]: {e}")
            except queue.Empty:
                continue
            except Exception:
                continue

    def get_stats(self):
        return [
            {
                'name': q_name,
                'messages': self._stats.get(q_name, 0),
                'consumers': 1 if q_name in self._handlers else 0,
                'pending': self._queues[q_name].qsize()
            }
            for q_name in self._queues
        ]

    def get_recent_messages(self, limit=20):
        return list(self._message_log)[:limit]

    def is_available(self):
        return True


inprocess_mq = InProcessMQ()
