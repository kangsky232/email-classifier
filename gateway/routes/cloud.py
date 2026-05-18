"""云原生组件路由"""
import logging
from flask import Blueprint, request, jsonify
from infrastructure.cloud_native.registry import service_registry
from infrastructure.cloud_native.config_center import config_center
from infrastructure.cloud_native.tracing import tracer
from infrastructure.cloud_native.circuit_breaker import circuit_breaker
from infrastructure.cloud_native.health import health_checker
from gateway.middleware import login_required
from infrastructure.database.models import sanitize_input

logger = logging.getLogger(__name__)
cloud_bp = Blueprint('cloud', __name__)


@cloud_bp.route('/api/cloud/services', methods=['GET'])
@login_required
def get_services():
    return jsonify(service_registry.get_all_services())


@cloud_bp.route('/api/cloud/services/register', methods=['POST'])
@login_required
def register_service():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    service_id = sanitize_input(data.get('service_id', ''), 100)
    service_name = sanitize_input(data.get('service_name', ''), 200)
    host = sanitize_input(data.get('host', '127.0.0.1'), 200)
    port = data.get('port', 0)
    metadata = data.get('metadata', {})
    if not service_id or not service_name:
        return jsonify({"error": "service_id and service_name required"}), 400
    if not isinstance(port, int) or port < 0 or port > 65535:
        port = 0
    if isinstance(metadata, dict) and len(str(metadata)) > 2000:
        return jsonify({"error": "metadata too large"}), 400
    instance = service_registry.register(service_id, service_name, host, port, metadata)
    return jsonify(instance.to_dict())


@cloud_bp.route('/api/cloud/services/heartbeat', methods=['POST'])
@login_required
def service_heartbeat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    service_name = sanitize_input(data.get('service_name', ''), 200)
    service_id = sanitize_input(data.get('service_id', ''), 100)
    if service_name and service_id:
        service_registry.heartbeat(service_name, service_id)
    return jsonify({"success": True})


@cloud_bp.route('/api/cloud/config', methods=['GET'])
@login_required
def get_config_center():
    namespace = sanitize_input(request.args.get('namespace', 'default'), 50)
    configs = config_center.get_all(namespace)
    return jsonify({"namespace": namespace, "configs": configs})


@cloud_bp.route('/api/cloud/config', methods=['POST'])
@login_required
def set_config_center():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    key = sanitize_input(data.get('key', ''), 200)
    value = data.get('value')
    namespace = sanitize_input(data.get('namespace', 'default'), 50)
    if not key:
        return jsonify({"error": "key required"}), 400
    if isinstance(value, str) and len(value) > 5000:
        return jsonify({"error": "value too large"}), 400
    config_center.set(key, value, namespace)
    return jsonify({"success": True})


@cloud_bp.route('/api/cloud/traces', methods=['GET'])
@login_required
def get_traces():
    limit = min(request.args.get('limit', 50, type=int), 1000)
    traces = tracer.get_recent_traces(limit)
    stats = tracer.get_stats()
    return jsonify({"traces": traces, "stats": stats})


@cloud_bp.route('/api/cloud/traces/<trace_id>', methods=['GET'])
@login_required
def get_trace_detail(trace_id):
    trace = tracer.get_trace(trace_id)
    return jsonify({"trace_id": trace_id, "spans": trace})


@cloud_bp.route('/api/cloud/circuit-breakers', methods=['GET'])
@login_required
def get_circuit_breakers():
    return jsonify(circuit_breaker.get_all_stats())


@cloud_bp.route('/api/cloud/health', methods=['GET'])
@login_required
def get_cloud_health():
    return jsonify(health_checker.check_all())


@cloud_bp.route('/api/cloud/health/live', methods=['GET'])
def liveness_probe():
    result = health_checker.liveness()
    status_code = 200 if result["status"] == "UP" else 503
    return jsonify(result), status_code


@cloud_bp.route('/api/cloud/health/ready', methods=['GET'])
def readiness_probe():
    result = health_checker.readiness()
    status_code = 200 if result["status"] == "UP" else 503
    return jsonify(result), status_code
