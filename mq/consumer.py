import pika
import json
import threading
from config import Config

class MQConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.handlers = {}
        self.running = False
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
        except Exception as e:
            print(f"RabbitMQ连接失败: {e}")
            self.connection = None
            self.channel = None
    
    def register_handler(self, queue, handler):
        self.handlers[queue] = handler
        if self.channel:
            self.channel.queue_declare(queue=queue, durable=True)
    
    def _on_message(self, channel, method, properties, body):
        try:
            message = json.loads(body)
            queue = method.routing_key
            
            if queue in self.handlers:
                result = self.handlers[queue](message)
                if result:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    channel.basic_nack(delivery_tag=method.delivery_tag)
            else:
                channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"处理消息失败: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag)
    
    def start_consuming(self):
        if not self.channel:
            self._connect()
        if not self.channel:
            print("无法启动消费者: RabbitMQ未连接")
            return
        
        self.running = True
        
        for queue in self.handlers:
            self.channel.basic_consume(
                queue=queue,
                on_message_callback=self._on_message,
                auto_ack=False
            )
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.running = False
    
    def start_async(self):
        thread = threading.Thread(target=self.start_consuming, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        self.running = False
        if self.channel:
            try:
                self.channel.stop_consuming()
            except:
                pass
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
    
    def get_queue_info(self):
        if not self.channel:
            self._connect()
        if not self.channel:
            return []
        
        queues = ['email_input', 'classification_result', 'paxos_proposal', 'final_action']
        info = []
        
        for queue in queues:
            try:
                method = self.channel.queue_declare(queue=queue, durable=True, passive=True)
                info.append({
                    "name": queue,
                    "messages": method.method.message_count,
                    "consumers": method.method.consumer_count
                })
            except:
                info.append({
                    "name": queue,
                    "messages": 0,
                    "consumers": 0
                })
        
        return info

consumer = MQConsumer()
