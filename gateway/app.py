"""API 网关主应用"""
import logging
import time
import os
import platform
import threading

import uuid
from flask import Flask, jsonify, render_template, request, g
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from config.settings import Config
from infrastructure.mq.producer import producer
from infrastructure.mq.handlers import register_all_handlers, set_classification_handler, set_app
from services.classifier.classifier import classifier
from services.storage.master import gfs_master
from services.storage.chunkserver import GFSChunkServer
from services.mapreduce.bayes import mapreduce_bayes
from infrastructure.cloud_native.registry import service_registry
from infrastructure.cloud_native.config_center import config_center
from infrastructure.cloud_native.tracing import tracer
from infrastructure.cloud_native.circuit_breaker import circuit_breaker
from infrastructure.cloud_native.health import health_checker, ProbeType
from infrastructure.cluster.monitor import cluster_monitor

# ============================================
# Logging
# ============================================
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# App Initialization
# ============================================
_start_time = time.time()

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, static_folder=os.path.join(_base_dir, 'static'), template_folder=os.path.join(_base_dir, 'templates'))
app.secret_key = Config.SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = Config.SESSION_TIMEOUT
CORS(app, supports_credentials=True, origins=Config.ALLOWED_ORIGINS)
socketio = SocketIO(app, cors_allowed_origins=Config.ALLOWED_ORIGINS)

# ============================================
# MQ Setup
# ============================================
MQ_AVAILABLE = False


def _check_mq_connection():
    global MQ_AVAILABLE
    MQ_AVAILABLE = producer.is_connected()
    if producer.using_rabbitmq():
        logger.info("RabbitMQ 已连接，消息队列功能可用")
    elif MQ_AVAILABLE:
        logger.info("内存队列模式（功能正常，消息不持久化）")
    else:
        logger.warning("消息队列不可用")


_check_mq_connection()
set_classification_handler(lambda **kwargs: classifier.classify(**kwargs))
set_app(app)
register_all_handlers()

# ============================================
# GFS ChunkServer
# ============================================
_chunk_servers = {}


def _get_chunk_server(server_id: str):
    if server_id not in _chunk_servers:
        _chunk_servers[server_id] = GFSChunkServer(
            server_id=server_id,
            master_url="http://127.0.0.1:5000"
        )
    return _chunk_servers[server_id]


# ============================================
# Register Blueprints
# ============================================
from gateway.routes.auth import auth_bp
from gateway.routes.emails import emails_bp, init_emails_routes
from gateway.routes.classify import classify_bp, init_classify_routes
from gateway.routes.stats import stats_bp
from gateway.routes.cloud import cloud_bp
from gateway.routes.cluster import cluster_bp, init_cluster_routes

app.register_blueprint(auth_bp)
app.register_blueprint(emails_bp)
app.register_blueprint(classify_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(cloud_bp)
app.register_blueprint(cluster_bp)

# Inject dependencies into routes
init_emails_routes(gfs_master, _get_chunk_server, producer, socketio)
init_classify_routes(socketio)
init_cluster_routes(gfs_master, _get_chunk_server)

# ============================================
# Background Threads
# ============================================


def _broadcast_agent_health():
    while True:
        try:
            time.sleep(15)
            agents = classifier.get_agents_status()
            socketio.emit('agent_health', {'agents': agents, 'timestamp': time.time()})
        except Exception as e:
            logger.debug(f"Agent health broadcast error: {e}")


def _service_heartbeat():
    while True:
        try:
            time.sleep(10)
            service_registry.heartbeat("email-classifier", "main-app")
            for node in classifier.acceptor_nodes:
                if node.is_available():
                    service_registry.heartbeat("llm-agent", node.id)
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")


threading.Thread(target=_broadcast_agent_health, daemon=True).start()
threading.Thread(target=_service_heartbeat, daemon=True).start()

# ============================================
# Cloud Native Initialization
# ============================================
service_registry.register("main-app", "email-classifier", "127.0.0.1", 5000, {"version": "1.0.0", "type": "web"})

for node in classifier.acceptor_nodes:
    try:
        port = int(node.url.split(":")[-1])
        service_registry.register(node.id, "llm-agent", "127.0.0.1", port, {"role": node.role, "name": node.name})
    except Exception:
        pass

service_registry.start_health_check(interval=15)
cluster_monitor.start(collection_interval=5)

health_checker.register("database", lambda: True, ProbeType.LIVENESS)
health_checker.register("message-queue", lambda: producer.is_connected(), ProbeType.READINESS)
health_checker.register("llm-agents", lambda: any(n.is_available() for n in classifier.acceptor_nodes), ProbeType.READINESS)
health_checker.start(interval=30)

config_center.set("app.name", "Email Classifier")
config_center.set("app.version", "1.0.0")
config_center.set("paxos.quorum", 3)
config_center.set("gfs.replicas", 3)

# 注册配置变更监听器
def _on_config_change(key, value):
    logger.info(f"Config changed: {key} = {value}")

config_center.watch("llm", "active_provider", _on_config_change)
config_center.watch("system", "DEEPSEEK_API_KEY", _on_config_change)

circuit_breaker.get_or_create("llm-agents", failure_threshold=3, recovery_timeout=30)
logger.info("Cloud native components initialized")

# ============================================
# Distributed Tracing Middleware
# ============================================

@app.before_request
def start_trace():
    if request.path in ('/api/health', '/api/cloud/health/live', '/api/cloud/health/ready'):
        return
    trace_id = request.headers.get('X-Trace-Id') or str(uuid.uuid4())[:16]
    g.trace_id = trace_id
    g.span = tracer.start_trace(request.path, "gateway")
    g.span.set_tag("http.method", request.method)
    g.span.set_tag("http.url", request.url)
    g.span.set_tag("trace_id", trace_id)


@app.after_request
def end_trace(response):
    span = getattr(g, 'span', None)
    if span:
        span.set_tag("http.status_code", response.status_code)
        if response.status_code >= 400:
            span.status = "ERROR"
        span.finish()
    return response


# ============================================
# Error Handlers
# ============================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "资源不存在"}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"error": "服务器内部错误"}), 500


# ============================================
# Index & Health
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "mq_available": MQ_AVAILABLE,
        "using_rabbitmq": producer.using_rabbitmq() if producer else False,
        "python_version": platform.python_version(),
        "agents": len(classifier.get_all_agents()),
        "uptime": round(time.time() - _start_time, 2)
    })


@socketio.on('connect')
def handle_connect():
    logger.info('WebSocket客户端已连接')


@socketio.on('disconnect')
def handle_disconnect():
    logger.info('WebSocket客户端已断开')


if __name__ == '__main__':
    import sys
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    if '--prod' in sys.argv:
        import eventlet
        eventlet.monkey_patch()
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
    else:
        socketio.run(app, debug=debug, host='0.0.0.0', port=port, allow_unsafe_werkzeug=debug)
