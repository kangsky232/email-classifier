"""集群监控、GFS、负载均衡、MapReduce、LLM 配置、队列、Paxos 路由"""
import logging
import os
import json
import time
from flask import Blueprint, request, jsonify
from infrastructure.database.models import SystemConfig, sanitize_input
from services.classifier.classifier import classifier
from services.classifier.llm_agent import LLMAgent, BUILTIN_PROVIDERS, _load_providers_from_env
from services.mapreduce.bayes import mapreduce_bayes
from infrastructure.cluster.consistent_hash import cluster_manager
from infrastructure.cluster.monitor import cluster_monitor
from infrastructure.cluster.load_balancer import load_balancer
from infrastructure.mq.producer import producer
from infrastructure.mq.consumer import consumer
from infrastructure.cloud_native.config_center import config_center
from gateway.middleware import login_required, rate_limit, _get_current_user

import requests as http_requests

logger = logging.getLogger(__name__)
cluster_bp = Blueprint('cluster', __name__)


def _mask_key(key):
    """脱敏 API Key，只显示前3位和后4位"""
    if not key or len(key) <= 8:
        return "***"
    return f"{key[:3]}***{key[-4:]}"

# GFS 依赖由 gateway/app.py 注入
_gfs_master = None
_get_chunk_server = None


def init_cluster_routes(gfs_master, get_chunk_server):
    global _gfs_master, _get_chunk_server
    _gfs_master = gfs_master
    _get_chunk_server = get_chunk_server


# ============================================
# Cluster Monitoring
# ============================================

@cluster_bp.route('/api/cluster/status', methods=['GET'])
@login_required
def get_cluster_status():
    return jsonify(cluster_manager.get_cluster_status())


@cluster_bp.route('/api/cluster/metrics', methods=['GET'])
@login_required
def get_cluster_metrics():
    local = cluster_monitor.get_local_metrics()
    cluster = cluster_monitor.get_cluster_metrics()
    nodes = cluster_monitor.get_all_node_metrics()
    return jsonify({"local": local, "cluster": cluster, "nodes": nodes})


@cluster_bp.route('/api/cluster/metrics/history/<metric>', methods=['GET'])
@login_required
def get_metric_history(metric):
    limit = request.args.get('limit', 60, type=int)
    history = cluster_monitor.get_metric_history(metric, limit)
    return jsonify({"metric": metric, "history": history})


@cluster_bp.route('/api/cluster/nodes', methods=['GET'])
@login_required
def get_cluster_nodes():
    nodes = cluster_manager.get_all_nodes()
    return jsonify({"nodes": nodes})


@cluster_bp.route('/api/cluster/hashring', methods=['GET'])
@login_required
def get_hashring_info():
    info = cluster_manager.hash_ring.get_ring_info()
    return jsonify(info)


# ============================================
# GFS Distributed Storage
# ============================================

@cluster_bp.route('/api/gfs/cluster', methods=['GET'])
@login_required
def get_gfs_cluster():
    return jsonify(_gfs_master.get_cluster_info())


@cluster_bp.route('/api/gfs/files', methods=['GET'])
@login_required
def get_gfs_files():
    files = _gfs_master.list_files()
    return jsonify({"files": [f.to_dict() for f in files]})


@cluster_bp.route('/api/gfs/files', methods=['POST'])
@login_required
def create_gfs_file():
    data = request.get_json()
    file_path = data.get('file_path', '')
    metadata = data.get('metadata', {})
    if not file_path:
        return jsonify({"error": "file_path required"}), 400
    file_id = _gfs_master.create_file(file_path, metadata)
    file_info = _gfs_master.get_file_info(file_id)
    return jsonify(file_info.to_dict())


@cluster_bp.route('/api/gfs/files/<file_id>', methods=['GET'])
@login_required
def get_gfs_file(file_id):
    file_info = _gfs_master.get_file_info(file_id)
    if not file_info:
        return jsonify({"error": "File not found"}), 404
    chunks = _gfs_master.get_file_chunks(file_id)
    return jsonify({"file": file_info.to_dict(), "chunks": [c.to_dict() for c in chunks]})


@cluster_bp.route('/api/gfs/files/<file_id>', methods=['PUT'])
@login_required
def update_gfs_file(file_id):
    data = request.get_json()
    file_info = _gfs_master.get_file_info(file_id)
    if not file_info:
        return jsonify({"error": "File not found"}), 404
    if 'size' in data:
        file_info.size = data['size']
    if 'chunk_count' in data:
        file_info.chunk_count = data['chunk_count']
    file_info.modified_at = time.time()
    _gfs_master._save_metadata()
    return jsonify(file_info.to_dict())


@cluster_bp.route('/api/gfs/files/<file_id>', methods=['DELETE'])
@login_required
def delete_gfs_file(file_id):
    success = _gfs_master.delete_file(file_id)
    return jsonify({"success": success})


@cluster_bp.route('/api/gfs/files/<file_id>/chunks', methods=['GET'])
@login_required
def get_gfs_file_chunks(file_id):
    chunks = _gfs_master.get_file_chunks(file_id)
    return jsonify([c.to_dict() for c in chunks])


@cluster_bp.route('/api/gfs/chunks/allocate', methods=['POST'])
@login_required
def allocate_gfs_chunk():
    data = request.get_json()
    file_id = data.get('file_id')
    chunk_index = data.get('chunk_index', 0)
    chunk_info = _gfs_master.allocate_chunk(file_id, chunk_index)
    if not chunk_info:
        return jsonify({"error": "Allocation failed"}), 500
    return jsonify(chunk_info.to_dict())


@cluster_bp.route('/api/gfs/chunks/write', methods=['POST'])
@login_required
def write_gfs_chunk():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    server_id = data.get('server_id')
    chunk_id = data.get('chunk_id')
    hex_data = data.get('data', '')
    if not server_id or not chunk_id:
        return jsonify({"error": "server_id and chunk_id required"}), 400
    if len(hex_data) > 10 * 1024 * 1024:  # 5MB max (hex = 2x bytes)
        return jsonify({"error": "data too large (max 5MB)"}), 400
    server = _get_chunk_server(server_id)
    chunk_data = bytes.fromhex(hex_data)
    success = server.write_chunk(chunk_id, chunk_data)
    return jsonify({"success": success})


@cluster_bp.route('/api/gfs/chunks/read', methods=['GET'])
@login_required
def read_gfs_chunk():
    server_id = request.args.get('server_id')
    chunk_id = request.args.get('chunk_id')
    if not server_id or not chunk_id:
        return jsonify({"error": "server_id and chunk_id required"}), 400
    server = _get_chunk_server(server_id)
    data = server.read_chunk(chunk_id)
    if data is None:
        return jsonify({"error": "Chunk not found"}), 404
    return jsonify({"data": data.hex(), "size": len(data)})


@cluster_bp.route('/api/gfs/chunkserver/register', methods=['POST'])
@login_required
def register_chunk_server():
    data = request.get_json()
    server_id = data.get('server_id')
    if not server_id:
        return jsonify({"error": "server_id required"}), 400
    _gfs_master.register_chunk_server(server_id, data)
    return jsonify({"success": True})


@cluster_bp.route('/api/gfs/heartbeat', methods=['POST'])
@login_required
def gfs_heartbeat():
    data = request.get_json()
    server_id = data.get('server_id')
    if server_id:
        _gfs_master.update_server_heartbeat(server_id)
    return jsonify({"success": True})


@cluster_bp.route('/api/gfs/chunkservers', methods=['GET'])
@login_required
def get_chunk_servers():
    return jsonify({"servers": _gfs_master.chunk_servers})


@cluster_bp.route('/api/gfs/rebalance', methods=['POST'])
@login_required
def rebalance_gfs():
    _gfs_master.rebalance_replicas()
    return jsonify({"success": True})


# ============================================
# Load Balancer
# ============================================

@cluster_bp.route('/api/lb/stats', methods=['GET'])
@login_required
def get_load_balancer_stats():
    return jsonify(load_balancer.get_stats())


@cluster_bp.route('/api/lb/select', methods=['POST'])
@login_required
def select_node():
    data = request.get_json() or {}
    strategy = data.get('strategy', 'health_aware')
    node_id = load_balancer.select_node(strategy)
    return jsonify({"node_id": node_id, "strategy": strategy})


@cluster_bp.route('/api/lb/record', methods=['POST'])
@login_required
def record_lb_request():
    data = request.get_json()
    node_id = data.get('node_id')
    response_time = data.get('response_time', 0)
    success = data.get('success', True)
    if node_id:
        load_balancer.record_request(node_id, response_time, success)
    return jsonify({"success": True})


# ============================================
# MapReduce Bayes
# ============================================

@cluster_bp.route('/api/mapreduce/stats', methods=['GET'])
@login_required
def get_mapreduce_stats():
    global_stats = mapreduce_bayes.get_global_stats()
    node_stats = mapreduce_bayes.get_node_stats()
    return jsonify({"global": global_stats, "nodes": node_stats})


@cluster_bp.route('/api/mapreduce/train', methods=['POST'])
@login_required
@rate_limit()
def mapreduce_train():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    node_id = data.get('node_id', 'local')
    documents = data.get('documents', [])
    if not documents:
        return jsonify({"error": "No documents provided"}), 400
    if len(documents) > 10000:
        return jsonify({"error": "Too many documents (max 10000)"}), 400
    result = mapreduce_bayes.map_phase(node_id, documents)
    return jsonify({"success": True, "result": result})


@cluster_bp.route('/api/mapreduce/reduce', methods=['POST'])
@login_required
def mapreduce_reduce():
    result = mapreduce_bayes.reduce_phase()
    return jsonify({"success": True, "result": result})


@cluster_bp.route('/api/mapreduce/predict', methods=['POST'])
@login_required
def mapreduce_predict():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "Text required"}), 400
    category, confidence, scores = mapreduce_bayes.predict(text)
    return jsonify({
        "category": category, "confidence": round(confidence, 4),
        "scores": {k: round(v, 4) for k, v in scores.items()}
    })


# ============================================
# LLM Config
# ============================================

@cluster_bp.route('/api/config', methods=['GET'])
@login_required
def get_config():
    config = SystemConfig.get_all()
    return jsonify(config)


@cluster_bp.route('/api/config', methods=['PUT'])
@login_required
@rate_limit()
def update_config():
    data = request.get_json()
    for key, value in data.items():
        SystemConfig.set(key, value)
        config_center.set(key, value, namespace="system")
        if key == 'DEEPSEEK_API_KEY':
            os.environ['DEEPSEEK_API_KEY'] = value
            for node in classifier.acceptor_nodes:
                try:
                    http_requests.post(f"{node.url}/health", timeout=2)
                except Exception:
                    pass
    logger.info("System config updated")
    return jsonify({"success": True})


@cluster_bp.route('/api/llm/status', methods=['GET'])
@login_required
def get_llm_status():
    # Use cached health status (updated by background thread)
    node_statuses = []
    for node in classifier.acceptor_nodes:
        node_statuses.append({
            "node_id": node.id, "name": node.name, "role": node.role,
            "url": node.url, "status": node.status, "health": None
        })

    providers = _load_providers_from_env()
    active_count = len(providers)
    active_count = len(providers)
    any_available = any(n["status"] == "online" for n in node_statuses)
    return jsonify({
        "available": any_available or active_count > 0,
        "total_nodes": len(node_statuses),
        "online_nodes": sum(1 for n in node_statuses if n["status"] == "online"),
        "nodes": node_statuses,
        "providers": {k: {"name": v["name"], "model": v.get("model", ""), "protocol": v.get("protocol", ""), "active": True} for k, v in providers.items()},
        "builtin_providers": {k: {"name": v["name"], "model": v.get("model", ""), "protocol": v.get("protocol", ""), "env_key": v.get("env_key")} for k, v in BUILTIN_PROVIDERS.items()},
        "active_providers": active_count,
        "total_providers": len(BUILTIN_PROVIDERS)
    })


@cluster_bp.route('/api/llm/config', methods=['POST'])
@login_required
@rate_limit()
def configure_llm():
    data = request.get_json()
    provider = sanitize_input(data.get('provider', 'deepseek'), 50)
    api_key = sanitize_input(data.get('api_key', ''), 200).strip()
    url = sanitize_input(data.get('url', ''), 500).strip()
    model = sanitize_input(data.get('model', ''), 100).strip()
    name = sanitize_input(data.get('name', ''), 100).strip()

    if not api_key:
        return jsonify({"success": False, "error": "API Key 不能为空"}), 400

    if provider == "custom":
        if not url:
            return jsonify({"success": False, "error": "自定义模型需要填写 URL"}), 400
        os.environ['CUSTOM_LLM_KEY'] = api_key
        os.environ['CUSTOM_LLM_URL'] = url
        os.environ['CUSTOM_LLM_MODEL'] = model or "default-model"
        os.environ['CUSTOM_LLM_NAME'] = name or "自定义模型"
        config_center.set("llm.provider", "custom", namespace="llm")
        config_center.set("llm.custom_url", url, namespace="llm")
    else:
        key_mapping = {
            'deepseek': 'DEEPSEEK_API_KEY', 'qwen': 'DASHSCOPE_API_KEY',
            'openai': 'OPENAI_API_KEY', 'ernie': 'ERNIE_API_KEY',
            'spark': 'SPARK_API_KEY', 'glm': 'ZHIPU_API_KEY'
        }
        env_key = key_mapping.get(provider)
        if env_key:
            os.environ[env_key] = api_key
            config_center.set(f"llm.{provider}_configured", True, namespace="llm")
    config_center.set("llm.active_provider", provider, namespace="llm")

    results = []
    for node in classifier.acceptor_nodes:
        try:
            resp = http_requests.post(
                f"{node.url}/config",
                json={"api_key": api_key, "provider": provider, "url": url, "model": model},
                timeout=5
            )
            results.append({
                "node": node.name, "success": resp.status_code == 200,
                "message": resp.json().get("message", "") if resp.status_code == 200 else "失败"
            })
        except Exception as e:
            results.append({"node": node.name, "success": False, "message": str(e)[:80]})

    success_count = sum(1 for r in results if r["success"])
    logger.info(f"LLM config updated: provider={provider}, synced to {success_count}/{len(results)} nodes")
    return jsonify({
        "success": True,
        "message": f"已同步到 {success_count}/{len(results)} 个节点（重启 agent_service 后生效）",
        "results": results
    })


@cluster_bp.route('/api/llm/agent-config', methods=['GET'])
@login_required
def get_agent_llm_config():
    roles = ["llm1", "llm2", "llm3", "llm4"]
    role_names = {"llm1": "LLM1", "llm2": "LLM2", "llm3": "LLM3", "llm4": "LLM4"}
    configs = {}
    for role in roles:
        saved = SystemConfig.get(f"agent_{role}_provider") or {}
        raw_key = saved.get("api_key", "")
        configs[role] = {
            "name": role_names.get(role, role),
            "provider_id": saved.get("provider_id", "ollama"),
            "api_key": _mask_key(raw_key) if raw_key else "",
            "base_url": saved.get("base_url", ""),
            "model": saved.get("model", ""),
            "custom_name": saved.get("custom_name", "")
        }
    all_providers = {}
    for pid, cfg in BUILTIN_PROVIDERS.items():
        all_providers[pid] = {"name": cfg["name"], "model": cfg.get("model", ""), "protocol": cfg.get("protocol", "")}
    return jsonify({"agents": configs, "providers": all_providers})


@cluster_bp.route('/api/llm/agent-config', methods=['POST'])
@login_required
@rate_limit()
def set_agent_llm_config():
    data = request.get_json()
    role = sanitize_input(data.get('role', ''), 50)
    provider_id = sanitize_input(data.get('provider_id', 'ollama'), 50)
    api_key = sanitize_input(data.get('api_key', ''), 300).strip()
    base_url = sanitize_input(data.get('base_url', ''), 500).strip()
    model = sanitize_input(data.get('model', ''), 200).strip()
    custom_name = sanitize_input(data.get('custom_name', ''), 100).strip()

    if role not in ("llm1", "llm2", "llm3", "llm4"):
        return jsonify({"success": False, "error": "无效的 Agent 角色"}), 400

    config = {
        "provider_id": provider_id, "api_key": api_key,
        "base_url": base_url, "model": model, "custom_name": custom_name
    }
    SystemConfig.set(f"agent_{role}_provider", json.dumps(config, ensure_ascii=False))

    # 同步到配置中心
    config_center.set(f"agent.{role}.provider", provider_id, namespace="llm")
    config_center.set(f"agent.{role}.model", model, namespace="llm")
    if base_url:
        config_center.set(f"agent.{role}.base_url", base_url, namespace="llm")

    for node in classifier.acceptor_nodes:
        if node.role == role and node.is_available():
            try:
                http_requests.post(f"{node.url}/config", json={
                    "provider": provider_id, "api_key": api_key,
                    "url": base_url, "model": model, "name": custom_name
                }, timeout=5)
            except Exception:
                pass

    role_names = {"llm1": "LLM1", "llm2": "LLM2", "llm3": "LLM3", "llm4": "LLM4"}
    logger.info(f"Agent {role} LLM config updated: provider={provider_id}")
    return jsonify({
        "success": True,
        "message": f"{role_names.get(role, role)} Agent 的模型已设置为 {provider_id}"
    })


# ============================================
# Paxos Demo
# ============================================

@cluster_bp.route('/api/paxos/demo-conflict', methods=['POST'])
@login_required
@rate_limit()
def paxos_demo_conflict():
    nodes = [n for n in classifier.acceptor_nodes if n.is_available()]
    if len(nodes) < 3:
        return jsonify({"success": False, "error": "需要 3 个 Acceptor 节点都在线", "online_nodes": len(nodes)}), 400

    urls = [n.url for n in nodes]
    log = []
    rounds = []

    for url in urls:
        try:
            http_requests.post(f"{url}/paxos/reset", timeout=3)
        except Exception:
            pass

    def phase(msg):
        log.append({"type": "info", "message": msg})

    phase("【初始状态】3 个 Acceptor 的 promised_id = None，accepted_id = None")
    phase("【第一轮】Proposer 提案 ID=1，值='会议通知'")

    r1_promises = 0
    r1_accepts = 0
    for url in urls:
        try:
            r = http_requests.post(f"{url}/paxos/prepare", json={"proposal_id": 1, "sender": "demo"}, timeout=3)
            if r.status_code == 200 and r.json().get("type") == "promise":
                r1_promises += 1
                phase(f"  ✅ {url.split(':')[-1]} → Promise")
            else:
                phase(f"  ❌ {url.split(':')[-1]} → Reject")
        except Exception:
            phase(f"  ⚠️ {url.split(':')[-1]} → 无响应")

    if r1_promises >= 2:
        phase(f"  Prepare 阶段通过 ({r1_promises}/3 ≥ 2)")
        for url in urls:
            try:
                r = http_requests.post(f"{url}/paxos/accept", json={"proposal_id": 1, "value": "会议通知", "sender": "demo"}, timeout=3)
                if r.status_code == 200 and r.json().get("type") == "accepted":
                    r1_accepts += 1
                    phase(f"  ✅ {url.split(':')[-1]} → Accepted")
                else:
                    phase(f"  ❌ {url.split(':')[-1]} → Reject")
            except Exception:
                phase(f"  ⚠️ {url.split(':')[-1]} → 无响应")
        if r1_accepts >= 2:
            phase(f"  Accept 阶段通过 ({r1_accepts}/3 ≥ 2) → 🎯 共识达成: '会议通知'")
            rounds.append({"id": 1, "value": "会议通知", "result": "success"})
        else:
            rounds.append({"id": 1, "value": "会议通知", "result": "accept_failed"})
    else:
        rounds.append({"id": 1, "value": "会议通知", "result": "prepare_failed"})

    phase("【第二轮】Proposer 提案 ID=2，值='可疑邮件' (编号更高)")
    r2_promises = 0
    r2_accepts = 0
    for url in urls:
        try:
            r = http_requests.post(f"{url}/paxos/prepare", json={"proposal_id": 2, "sender": "demo"}, timeout=3)
            if r.status_code == 200 and r.json().get("type") == "promise":
                r2_promises += 1
                phase(f"  ✅ {url.split(':')[-1]} → Promise (2 > 1, 接受)")
            else:
                phase(f"  ❌ {url.split(':')[-1]} → Reject")
        except Exception:
            phase(f"  ⚠️ {url.split(':')[-1]} → 无响应")

    if r2_promises >= 2:
        phase(f"  Prepare 阶段通过 ({r2_promises}/3 ≥ 2)")
        for url in urls:
            try:
                r = http_requests.post(f"{url}/paxos/accept", json={"proposal_id": 2, "value": "可疑邮件", "sender": "demo"}, timeout=3)
                if r.status_code == 200 and r.json().get("type") == "accepted":
                    r2_accepts += 1
                    phase(f"  ✅ {url.split(':')[-1]} → Accepted")
                else:
                    phase(f"  ❌ {url.split(':')[-1]} → Reject")
            except Exception:
                phase(f"  ⚠️ {url.split(':')[-1]} → 无响应")
        if r2_accepts >= 2:
            phase(f"  Accept 阶段通过 ({r2_accepts}/3 ≥ 2) → 🎯 共识达成: '可疑邮件'")
            rounds.append({"id": 2, "value": "可疑邮件", "result": "success"})
        else:
            rounds.append({"id": 2, "value": "可疑邮件", "result": "accept_failed"})
    else:
        rounds.append({"id": 2, "value": "可疑邮件", "result": "prepare_failed"})

    phase("【⭐ 关键】用旧 ID=1 重新发起 Prepare → 应被拒绝！(已承诺 ID=2)")
    r3_promises = 0
    for url in urls:
        try:
            r = http_requests.post(f"{url}/paxos/prepare", json={"proposal_id": 1, "sender": "demo"}, timeout=3)
            if r.status_code == 200 and r.json().get("type") == "promise":
                r3_promises += 1
                phase(f"  ✅ {url.split(':')[-1]} → Promise (不应该!)")
            else:
                reason = r.json().get("value", "") if r.status_code == 200 else ""
                phase(f"  ❌ {url.split(':')[-1]} → Reject: {reason}")
        except Exception:
            phase(f"  ⚠️ {url.split(':')[-1]} → 无响应")

    if r3_promises < 2:
        phase(f"  Prepare 阶段失败 ({r3_promises}/3 < 2) → 🔒 已承诺更高 ID=2，旧 ID=1 被拒绝")
        phase("【结论】Paxos 通过 proposal_id 保证了一致性。一旦承诺更高编号，旧编号提案被永久拒绝。")
        rounds.append({"id": 1, "value": "会议通知", "result": "rejected"})
    else:
        rounds.append({"id": 1, "value": "会议通知", "result": "unexpected"})

    return jsonify({"success": True, "log": log, "rounds": rounds})


# ============================================
# Queue Status
# ============================================

@cluster_bp.route('/api/queue/status', methods=['GET'])
@login_required
def get_queue_status():
    return jsonify({
        "mq_available": producer.is_connected(),
        "using_rabbitmq": producer.using_rabbitmq(),
        "mode": "RabbitMQ" if producer.using_rabbitmq() else "内存队列",
        "queues": consumer.get_queue_info()
    })


@cluster_bp.route('/api/queue/messages', methods=['GET'])
@login_required
def get_queue_messages():
    limit = request.args.get('limit', 20, type=int)
    messages = consumer.get_recent_messages(limit)
    return jsonify({
        "mq_available": producer.is_connected(),
        "using_rabbitmq": producer.using_rabbitmq(),
        "messages": messages, "total": len(messages)
    })
