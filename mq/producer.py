import pika
import json
from config import Config
from mq.inprocess_queue import inprocess_mq


class MQProducer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self._using_rmq = False
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
            print("RabbitMQ 已连接，消息队列功能可用")
        except Exception as e:
            print(f"RabbitMQ连接失败: {e}")
            print("已切换到内存队列模式（功能正常，消息不持久化）")
            self.connection = None
            self.channel = None
            self._using_rmq = False

    def send_message(self, queue, message):
        if self._using_rmq:
            return self._send_rmq(queue, message)
        return self._send_inprocess(queue, message)

    def _send_rmq(self, queue, message):
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
            print(f"RabbitMQ 发送失败，切换到内存队列: {e}")
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
        if self.connection:
            try:
                self.connection.close()
            except:
                pass


producer = MQProducer()