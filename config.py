import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_NAME = os.getenv('DB_NAME', 'mail_system')
    
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')
    
    CATEGORIES = ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"]
    
    PAXOS_ACCEPTOR_COUNT = 3
    PAXOS_TIMEOUT_MS = 5000
    PAXOS_RETRY_COUNT = 3
    AGENT_MIN_COUNT = 2
    
    REMOTE_AGENTS = []

    ACCEPTOR_NODES = [
        {"id": "acceptor-1", "name": "安全专家", "role": "security",
         "url": os.getenv("ACCEPTOR_1_URL", "http://127.0.0.1:8503"), "port": 8503},
        {"id": "acceptor-2", "name": "商务助理", "role": "business",
         "url": os.getenv("ACCEPTOR_2_URL", "http://127.0.0.1:8504"), "port": 8504},
        {"id": "acceptor-3", "name": "通用分类", "role": "general",
         "url": os.getenv("ACCEPTOR_3_URL", "http://127.0.0.1:8505"), "port": 8505},
    ]

    @staticmethod
    def get_db_url():
        return f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
