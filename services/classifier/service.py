"""
LLM Agent 节点服务

启动方式（4个终端窗口）:
  python agent_service.py --role llm1 --port 8503 --id acceptor-1
  python agent_service.py --role llm2 --port 8504 --id acceptor-2
  python agent_service.py --role llm3 --port 8505 --id acceptor-3
  python agent_service.py --role llm4 --port 8506 --id acceptor-4

每个节点对外提供:
  GET  /health         - 健康检查
  POST /classify       - Agent 分类邮件
  POST /paxos/vote     - 投票判断是否同意提议
  GET  /stats          - 节点统计
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from services.classifier.llm_agent import LLMAgent
from services.consensus.acceptor import Acceptor
from services.consensus.message import Message, MessageType
from infrastructure.cloud_native.tracing import tracer
import argparse
import time
import uuid
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.before_request
def extract_trace():
    trace_id = request.headers.get('X-Trace-Id')
    if trace_id:
        g.trace_id = trace_id
        g.span = tracer.start_trace(request.path, "agent")
        g.span.set_tag("trace_id", trace_id)
        g.span.set_tag("http.method", request.method)


@app.after_request
def end_trace(response):
    span = getattr(g, 'span', None)
    if span:
        span.set_tag("http.status_code", response.status_code)
        span.finish()
    return response

agent = None
acceptor = None
instance_id = str(uuid.uuid4())[:6]
start_time = time.time()
request_count = 0


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "instance_id": instance_id,
        "node_id": acceptor.id if acceptor else "unknown",
        "agent_name": agent.name if agent else "unknown",
        "agent_role": agent.role if agent else "unknown",
        "agent_available": (agent._providers and len(agent._providers) > 0) if agent else False,
        "uptime_seconds": round(time.time() - start_time, 2),
        "request_count": request_count
    })


@app.route('/classify', methods=['POST'])
def classify():
    global request_count
    request_count += 1

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({"success": False, "error": "邮件内容不能为空"}), 400

    sender = data.get('sender', '')
    subject = data.get('subject', '')
    content = data.get('content', '')

    try:
        result = agent.classify(sender, subject, content)
        return jsonify({
            "success": True,
            "agent_name": agent.name,
            "agent_role": agent.role,
            "method": agent.method,
            "node_id": acceptor.id,
            "instance_id": instance_id,
            "result": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "agent_name": agent.name,
            "error": str(e)
        }), 500

@app.route('/generate-email', methods=['POST'])
def generate_email():
    global request_count
    request_count += 1

    data = request.get_json()
    keywords = data.get('keywords', '')
    if not keywords:
        return jsonify({"success": False, "error": "关键词不能为空"}), 400

    result = agent.generate_email(keywords)
    if result:
        return jsonify({"success": True, "email": result})
    return jsonify({"success": False, "error": "生成失败，请检查 API Key 配置"}), 503


@app.route('/paxos/prepare', methods=['POST'])
def paxos_prepare():
    data = request.get_json()
    proposal_id = data.get('proposal_id', 0)
    sender = data.get('sender', 'unknown')

    msg = Message.create_prepare(proposal_id, sender=sender)
    response = acceptor.handle_prepare(msg)

    return jsonify(response.to_dict())


@app.route('/paxos/accept', methods=['POST'])
def paxos_accept():
    data = request.get_json()
    proposal_id = data.get('proposal_id', 0)
    value = data.get('value', '')
    sender = data.get('sender', 'unknown')

    msg = Message.create_accept(proposal_id, value, sender=sender)
    response = acceptor.handle_accept(msg)

    return jsonify(response.to_dict())


@app.route('/paxos/vote', methods=['POST'])
def paxos_vote():
    """判断是否同意提议的分类"""
    global request_count
    request_count += 1

    data = request.get_json()
    content = data.get('content', '')
    proposed_category = data.get('proposed_category', '')
    proposed_reason = data.get('proposed_reason', '')

    if not content or not proposed_category:
        return jsonify({"success": False, "error": "参数不完整"}), 400

    try:
        result = agent.vote(content, proposed_category, proposed_reason)
        return jsonify({
            "success": True,
            "agent_name": agent.name,
            "node_id": acceptor.id,
            "vote": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "agent_name": agent.name,
            "error": str(e)
        }), 500


@app.route('/stats', methods=['GET'])
def stats():
    agent_stats = agent.get_stats() if agent else {}
    return jsonify({
        "agent": agent_stats,
        "acceptor_id": acceptor.id if acceptor else "unknown",
        "acceptor_log": acceptor.log[-5:] if acceptor else [],
        "instance_id": instance_id,
        "uptime_seconds": round(time.time() - start_time, 2),
        "request_count": request_count
    })


@app.route('/config', methods=['POST'])
def set_config():
    data = request.get_json()
    provider = data.get('provider', 'deepseek')
    api_key = data.get('api_key', '')

    if not api_key:
        return jsonify({"success": False, "error": "API Key 不能为空"}), 400

    import os

    if provider == "custom":
        os.environ['CUSTOM_LLM_KEY'] = api_key
        os.environ['CUSTOM_LLM_URL'] = data.get('url', '')
        os.environ['CUSTOM_LLM_MODEL'] = data.get('model', 'default-model')
        os.environ['CUSTOM_LLM_NAME'] = data.get('name', '自定义模型')
    else:
        key_mapping = {
            'deepseek': 'DEEPSEEK_API_KEY',
            'qwen': 'DASHSCOPE_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'ernie': 'ERNIE_API_KEY',
            'spark': 'SPARK_API_KEY',
            'glm': 'ZHIPU_API_KEY'
        }
        env_key = key_mapping.get(provider, 'DEEPSEEK_API_KEY')
        os.environ[env_key] = api_key

    agent._refresh_providers()
    return jsonify({"success": True, "message": f"{provider} API Key 已更新，节点 {acceptor.id} 已就绪"})


@app.route('/paxos/state', methods=['GET'])
def paxos_state():
    """查看 Acceptor 当前状态（用于演示 Paxos 两阶段协议）"""
    return jsonify({
        "acceptor_id": acceptor.id,
        "promised_id": acceptor.promised_id,
        "accepted_id": acceptor.accepted_id,
        "accepted_value": acceptor.accepted_value,
        "log": acceptor.log[-10:]
    })


@app.route('/paxos/reset', methods=['POST'])
def paxos_reset():
    """重置 Acceptor 状态（用于重新演示）"""
    acceptor.reset()
    return jsonify({"success": True, "message": f"{acceptor.id} 状态已重置"})


@app.route('/paxos/log', methods=['GET'])
def paxos_log():
    return jsonify({
        "acceptor_id": acceptor.id,
        "log": acceptor.log[-20:]
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LLM Agent 节点服务')
    parser.add_argument('--role', type=str, default='llm1',
                        choices=['llm1', 'llm2', 'llm3', 'llm4'],
                        help='Agent 角色: llm1/llm2/llm3/llm4')
    parser.add_argument('--port', type=int, default=8503, help='服务端口')
    parser.add_argument('--id', type=str, default='acceptor-1', help='Acceptor ID')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    args = parser.parse_args()

    agent = LLMAgent(role=args.role)
    acceptor = Acceptor(args.id)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    logger.info("=" * 40)
    logger.info(f"  LLM Agent 节点已启动")
    logger.info(f"  ID:     {args.id}")
    logger.info(f"  Agent:  {agent.name}")
    logger.info(f"  Role:   {agent.role}")
    logger.info(f"  API:    {args.host}:{args.port}")
    logger.info(f"  实例:   {instance_id}")
    logger.info(f"  LLM:    {'已配置(' + str(len(agent._providers)) + '个Provider)' if agent._providers else '未配置'}")
    logger.info("=" * 40)

    app.run(host=args.host, port=args.port, debug=False)
