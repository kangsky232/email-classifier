import pika
import json
import threading
import logging
from config.settings import Config
from infrastructure.mq.inprocess_queue import inprocess_mq

logger = logging.getLogger(__name__)


class MQProducer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self._using_rmq = False
        self._lock = threading.Lock()
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
            logger.info("RabbitMQ connected, message queue available")
        except Exception as e:
            logger.warning(f"RabbitMQ connection failed: {e}")
            logger.info("Switched to in-process queue mode (messages not persisted)")
            self.connection = None
            self.channel = None
            self._using_rmq = False

    def send_message(self, queue, message):
        if self._using_rmq:
            return self._send_rmq(queue, message)
        return self._send_inprocess(queue, message)

    def _send_rmq(self, queue, message):
        with self._lock:
            if not self.channel:
                self._connect()
            if not self.channel:
                self._using_rmq = False
                return self._send_inprocess(queue, message)
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            return True
        except Exception as e:
            logger.error(f"RabbitMQ send failed, switching to in-process queue: {e}")
            self._using_rmq = False
            return self._send_inprocess(queue, message)

    def _send_inprocess(self, queue, message):
        return inprocess_mq.publish(queue, message)

    def send_email(self, email_data):
        return self.send_message('email_input', {
            'type': 'new_email',
            'data': email_data
        })

    def send_classification(self, result_data):
        return self.send_message('classification_result', {
            'type': 'classification_result',
            'data': result_data
        })

    def send_proposal(self, proposal_data):
        return self.send_message('paxos_proposal', {
            'type': 'paxos_proposal',
            'data': proposal_data
        })

    def send_final_action(self, action_data):
        return self.send_message('final_action', {
            'type': 'final_action',
            'data': action_data
        })

    def is_connected(self):
        return self._using_rmq or inprocess_mq.is_available()

    def using_rabbitmq(self):
        return self._using_rmq

    def close(self):
        if self.channel:
            try:
                self.channel.close()
            except Exception as e:
                logger.warning(f"Error closing MQ channel: {e}")
        if self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.warning(f"Error closing MQ connection: {e}")
        logger.info("MQ Producer closed")


producer = MQProducer()
