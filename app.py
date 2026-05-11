from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from config import Config
from database.models import Email, Classification, PaxosLog, FinalResult, SystemConfig
from agents.classifier import classifier
from mq.producer import producer
from mq.consumer import consumer
import threading

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/emails', methods=['GET'])
def get_emails():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    search = request.args.get('search', None)
    category = request.args.get('category', None)
    result = Email.get_list(page, limit, search, category)
    return jsonify(result)

@app.route('/api/emails', methods=['POST'])
def create_email():
    data = request.get_json()
    if not data or not data.get('sender'):
        return jsonify({"error": "发件人不能为空"}), 400
    
    email_id = Email.create(
        sender=data.get('sender', ''),
        subject=data.get('subject', ''),
        content=data.get('content', '')
    )
    
    producer.send_email({
        "email_id": email_id,
        "sender": data.get('sender', ''),
        "subject": data.get('subject', ''),
        "content": data.get('content', '')
    })
    
    email = Email.get_by_id(email_id)
    return jsonify({"success": True, "email": email})

@app.route('/api/emails/<int:email_id>', methods=['GET'])
def get_email(email_id):
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    
    classifications = Classification.get_by_email(email_id)
    final_result = FinalResult.get_by_email(email_id)
    paxos_logs = PaxosLog.get_by_email(email_id)
    
    return jsonify({
        "email": email,
        "classifications": classifications,
        "final_result": final_result,
        "paxos_logs": paxos_logs
    })

@app.route('/api/emails/<int:email_id>', methods=['PUT'])
def update_email(email_id):
    data = request.get_json()
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    
    Email.update(
        email_id,
        sender=data.get('sender', email['sender']),
        subject=data.get('subject', email['subject']),
        content=data.get('content', email['content'])
    )
    
    return jsonify({"success": True})

@app.route('/api/emails/<int:email_id>', methods=['DELETE'])
def delete_email(email_id):
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    
    Email.delete(email_id)
    return jsonify({"success": True})

@app.route('/api/emails/batch', methods=['POST'])
def batch_emails():
    data = request.get_json()
    action = data.get('action')
    email_ids = data.get('email_ids', [])
    
    if not email_ids:
        return jsonify({"error": "未选择邮件"}), 400
    
    results = []
    for email_id in email_ids:
        try:
            if action == 'delete':
                Email.delete(email_id)
                results.append({"email_id": email_id, "success": True})
            elif action == 'classify':
                email = Email.get_by_id(email_id)
                if email:
                    result = classifier.classify(
                        email_id=email_id,
                        sender=email['sender'],
                        subject=email['subject'],
                        content=email['content']
                    )
                    results.append({"email_id": email_id, "success": True, "result": result})
            else:
                results.append({"email_id": email_id, "success": False, "error": "未知操作"})
        except Exception as e:
            results.append({"email_id": email_id, "success": False, "error": str(e)})
    
    return jsonify({"results": results, "total": len(email_ids)})

@app.route('/api/classify', methods=['POST'])
def classify_email():
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({"error": "邮件内容不能为空"}), 400
    
    email_id = Email.create(
        sender=data.get('sender', 'unknown'),
        subject=data.get('subject', ''),
        content=data.get('content', '')
    )
    
    socketio.emit('classify_progress', {
        'email_id': email_id,
        'stage': 'started',
        'message': '开始分类...'
    })
    
    result = classifier.classify(
        email_id=email_id,
        sender=data.get('sender', ''),
        subject=data.get('subject', ''),
        content=data.get('content', '')
    )
    
    socketio.emit('classify_progress', {
        'email_id': email_id,
        'stage': 'completed',
        'result': result
    })
    
    producer.send_classification({
        "email_id": email_id,
        "result": result
    })
    
    return jsonify(result)

@app.route('/api/classify/<int:email_id>/result', methods=['GET'])
def get_classify_result(email_id):
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    
    classifications = Classification.get_by_email(email_id)
    final_result = FinalResult.get_by_email(email_id)
    paxos_logs = PaxosLog.get_by_email(email_id)
    
    return jsonify({
        "email_id": email_id,
        "email": email,
        "classifications": classifications,
        "final_result": final_result,
        "paxos_logs": paxos_logs
    })

@app.route('/api/agents/status', methods=['GET'])
def get_agents_status():
    status = classifier.get_agents_status()
    return jsonify({"agents": status})

@app.route('/api/agents/stats', methods=['GET'])
def get_agents_stats():
    stats = classifier.get_agents_stats()
    return jsonify(stats)

@app.route('/api/agents/remote', methods=['GET'])
def get_remote_agents():
    return jsonify({"remote_agents": [a.get_stats() for a in classifier.remote_agents]})

@app.route('/api/agents/remote', methods=['POST'])
def add_remote_agent():
    data = request.get_json()
    name = data.get('name', 'Remote')
    method = data.get('method', 'remote')
    url = data.get('url')
    timeout = data.get('timeout', 10)
    
    if not url:
        return jsonify({"error": "URL不能为空"}), 400
    
    result = classifier.add_remote_agent(name, method, url, timeout)
    return jsonify({"success": True, "agent": result})

@app.route('/api/agents/remote', methods=['DELETE'])
def remove_remote_agent():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "URL不能为空"}), 400
    
    classifier.remove_remote_agent(url)
    return jsonify({"success": True})

@app.route('/api/agents/remote/refresh', methods=['POST'])
def refresh_remote_agents():
    results = []
    for agent in classifier.remote_agents:
        online = agent.check_health()
        results.append({
            "url": agent.url,
            "name": agent.name,
            "status": agent.status,
            "online": online
        })
    return jsonify({"success": True, "agents": results})

@app.route('/api/paxos/logs', methods=['GET'])
def get_paxos_logs():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    email_id = request.args.get('email_id', None, type=int)
    result = PaxosLog.get_list(page, limit, email_id)
    return jsonify(result)

@app.route('/api/paxos/logs/<int:email_id>', methods=['GET'])
def get_paxos_logs_by_email(email_id):
    logs = PaxosLog.get_by_email(email_id)
    return jsonify({"email_id": email_id, "logs": logs})

@app.route('/api/stats/overview', methods=['GET'])
def get_stats_overview():
    stats = FinalResult.get_stats()
    return jsonify(stats)

@app.route('/api/stats/categories', methods=['GET'])
def get_stats_categories():
    stats = FinalResult.get_stats()
    return jsonify({"categories": stats.get("categories", [])})

@app.route('/api/stats/trends', methods=['GET'])
def get_stats_trends():
    stats = FinalResult.get_stats()
    return jsonify({"trends": stats.get("trends", [])})

@app.route('/api/stats/agents', methods=['GET'])
def get_stats_agents():
    stats = Classification.get_agent_stats()
    return jsonify({"agents": stats})

@app.route('/api/config', methods=['GET'])
def get_config():
    config = SystemConfig.get_all()
    return jsonify(config)

@app.route('/api/config', methods=['PUT'])
def update_config():
    data = request.get_json()
    for key, value in data.items():
        SystemConfig.set(key, value)
        if key == 'DASHSCOPE_API_KEY':
            import os
            os.environ['DASHSCOPE_API_KEY'] = value
            for agent in classifier.local_agents:
                if hasattr(agent, 'api_key'):
                    agent.api_key = value
                    agent.available = bool(value)
    return jsonify({"success": True})

@app.route('/api/llm/status', methods=['GET'])
def get_llm_status():
    llm_agent = None
    for agent in classifier.local_agents:
        if agent.__class__.__name__ == 'LLMAgent':
            llm_agent = agent
            break
    
    if llm_agent:
        return jsonify(llm_agent.get_status())
    
    return jsonify({
        "available": False,
        "total_providers": 0,
        "active_providers": 0,
        "providers": {},
        "available_list": []
    })

@app.route('/api/llm/config', methods=['POST'])
def configure_llm():
    data = request.get_json()
    api_key = data.get('api_key', '')
    provider = data.get('provider', 'qwen')
    model = data.get('model', '')

    import os
    
    key_mapping = {
        'qwen': 'DASHSCOPE_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'ernie': 'ERNIE_API_KEY',
        'spark': 'SPARK_API_KEY',
        'glm': 'ZHIPU_API_KEY'
    }
    
    env_key = key_mapping.get(provider)
    if env_key and api_key:
        os.environ[env_key] = api_key
    
    for agent in classifier.local_agents:
        if agent.__class__.__name__ == 'LLMAgent':
            agent._init_providers()
            break

    return jsonify({"success": True, "message": f"{provider} API Key已更新"})

@app.route('/api/queue/status', methods=['GET'])
def get_queue_status():
    try:
        queues = consumer.get_queue_info()
        return jsonify({"queues": queues})
    except:
        return jsonify({"queues": []})

@socketio.on('connect')
def handle_connect():
    print('WebSocket客户端已连接')

@socketio.on('disconnect')
def handle_disconnect():
    print('WebSocket客户端已断开')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
