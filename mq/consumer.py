import pika
import json
import threading
from config import Config
from mq.inprocess_queue import inprocess_mq


class MQConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self._using_rmq = False
        self._callbacks = {}
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
        except Exception as e:
            print(f"RabbitMQ Consumer 连接失败: {e}")
            print("Consumer 已切换到内存队列模式")
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
        def _callback(ch, method, properties, body):
            try:
                message = json.loads(body)
                callback(message)
            except Exception as e:
                print(f"RMQ 消息处理错误 [{queue}]: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(queue=queue, on_message_callback=_callback)
        t = threading.Thread(target=self._run_rmq, args=(queue,), daemon=True)
        t.start()

    def _run_rmq(self, queue_name):
        try:
            self.channel.start_consuming()
        except Exception as e:
            print(f"RMQ Consumer 断开 [{queue_name}]: {e}")

    def _start_inprocess_consumers(self):
        inprocess_mq.start_consuming()

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
            except:
                pass
        return inprocess_mq.get_stats()

    def get_recent_messages(self, limit=20):
        return inprocess_mq.get_recent_messages()

    def is_connected(self):
        return self._using_rmq


consumer = MQConsumer()