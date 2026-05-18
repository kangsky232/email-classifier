import pika
import json
import threading
import time
import logging
from collections import deque
from config.settings import Config
from infrastructure.mq.inprocess_queue import inprocess_mq

logger = logging.getLogger(__name__)


class MQConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self._using_rmq = False
        self._callbacks = {}
        self._message_log = deque(maxlen=50)
        self._connect()

    def _connect(self):
        try:
            credentials = pika.PlainCredentials(Config.RABBITMQ_USER, Config.RABBITMQ_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=Config.RABBITMQ_HOST,
                port=Config.RABBITMQ_PORT,
                credentials=credentials
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            self.channel.queue_declare(queue='email_input', durable=True)
            self.channel.queue_declare(queue='classification_result', durable=True)
            self.channel.queue_declare(queue='paxos_proposal', durable=True)
            self.channel.queue_declare(queue='final_action', durable=True)
            self._using_rmq = True
            logger.info("RabbitMQ Consumer connected")
        except Exception as e:
            logger.warning(f"RabbitMQ Consumer connection failed: {e}")
            logger.info("Consumer switched to in-process queue mode")
            self.connection = None
            self.channel = None
            self._using_rmq = False
            self._start_inprocess_consumers()

    def register_handler(self, queue, callback):
        self._callbacks[queue] = callback
        if self._using_rmq:
            self._start_rmq_consumer(queue, callback)
        else:
            inprocess_mq.subscribe(queue, callback)

    def _start_rmq_consumer(self, queue, callback):
        def _run_consumer():
            retry_delay = 2
            max_delay = 60
            while True:
                try:
                    conn = pika.BlockingConnection(pika.ConnectionParameters(
                        host=Config.RABBITMQ_HOST,
                        port=Config.RABBITMQ_PORT,
                        credentials=pika.PlainCredentials(Config.RABBITMQ_USER, Config.RABBITMQ_PASSWORD),
                        heartbeat=600,
                        blocked_connection_timeout=300
                    ))
                    ch = conn.channel()
                    ch.queue_declare(queue=queue, durable=True)
                    ch.basic_qos(prefetch_count=1)
                    retry_delay = 2  # 连接成功，重置退避

                    def _callback(ch, method, properties, body):
                        try:
                            message = json.loads(body)
                            self._log_message(queue, message)
                            callback(message)
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                        except Exception as e:
                            logger.error(f"RMQ message handling error [{queue}]: {e}")
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

                    ch.basic_consume(queue=queue, on_message_callback=_callback)
                    logger.info(f"RMQ consumer started [{queue}]")
                    ch.start_consuming()
                except Exception as e:
                    logger.error(f"RMQ Consumer disconnected [{queue}]: {e}, reconnecting in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_delay)

        t = threading.Thread(target=_run_consumer, daemon=True)
        t.start()

    def _start_inprocess_consumers(self):
        inprocess_mq.start_consuming()

    def _log_message(self, queue_name, message):
        entry = {
            'queue': queue_name,
            'data': message,
            'timestamp': time.time()
        }
        self._message_log.appendleft(entry)

    def get_queue_info(self):
        if self._using_rmq:
            try:
                queues = []
                for q_name in ['email_input', 'classification_result', 'paxos_proposal', 'final_action']:
                    q = self.channel.queue_declare(queue=q_name, durable=True, passive=True)
                    queues.append({
                        'name': q_name,
                        'messages': q.method.message_count,
                        'consumers': q.method.consumer_count
                    })
                return queues
            except Exception as e:
                logger.error(f"Failed to get RMQ queue info: {e}")
        return inprocess_mq.get_stats()

    def get_recent_messages(self, limit=20):
        if self._message_log:
            return self._message_log[:limit]
        return inprocess_mq.get_recent_messages(limit)

    def is_connected(self):
        return self._using_rmq


consumer = MQConsumer()
