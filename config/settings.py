import os
import secrets
from dotenv import load_dotenv

load_dotenv()

def _get_or_create_secret_key():
    env_key = os.getenv('SECRET_KEY')
    if env_key:
        return env_key
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.secret_key')
    key_file = os.path.normpath(key_file)
    if os.path.exists(key_file):
        with open(key_file, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            if len(key) >= 32:
                return key
    key = secrets.token_hex(32)
    try:
        with open(key_file, 'w', encoding='utf-8') as f:
            f.write(key)
    except OSError:
        pass
    return key


class Config:
    SECRET_KEY = _get_or_create_secret_key()

    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_NAME = os.getenv('DB_NAME', 'mail_system')
    DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 10))

    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')

    CATEGORIES = ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"]

    PAXOS_ACCEPTOR_COUNT = 4
    PAXOS_TIMEOUT_MS = 5000
    PAXOS_RETRY_COUNT = 3
    AGENT_MIN_COUNT = 2

    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',')
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 60))
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', 3600))

    REMOTE_AGENTS = []

    ACCEPTOR_NODES = [
        {"id": "acceptor-1", "name": "LLM1", "role": "llm1",
         "url": os.getenv("ACCEPTOR_1_URL", "http://127.0.0.1:8503"), "port": 8503},
        {"id": "acceptor-2", "name": "LLM2", "role": "llm2",
         "url": os.getenv("ACCEPTOR_2_URL", "http://127.0.0.1:8504"), "port": 8504},
        {"id": "acceptor-3", "name": "LLM3", "role": "llm3",
         "url": os.getenv("ACCEPTOR_3_URL", "http://127.0.0.1:8505"), "port": 8505},
        {"id": "acceptor-4", "name": "LLM4", "role": "llm4",
         "url": os.getenv("ACCEPTOR_4_URL", "http://127.0.0.1:8506"), "port": 8506},
    ]

    @staticmethod
    def get_db_url():
        return f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
