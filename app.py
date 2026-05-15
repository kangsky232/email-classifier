from flask import Flask, request, jsonify, render_template, session, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from config import Config
from database.models import Email, Classification, PaxosLog, FinalResult, SystemConfig, User
from agents.classifier import classifier
from agents.llm_agent import LLMAgent
from mq.producer import producer
from mq.consumer import consumer
import threading
import requests
import time
import csv
import io
import os
from collections import Counter

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = Config.SECRET_KEY
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*")

MQ_AVAILABLE = False

def _check_mq_connection():
    global MQ_AVAILABLE
    MQ_AVAILABLE = producer.is_connected()
    if producer.using_rabbitmq():
        print("RabbitMQ 已连接，消息队列功能可用")
    elif MQ_AVAILABLE:
        print("内存队列模式（功能正常，消息不持久化）")
    else:
        print("消息队列不可用")

_check_mq_connection()

def _get_current_user():
    if "user_id" in session:
        return session.get("user_id")
    return None

# ============================================
# Auth
# ============================================

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if len(username) < 2 or len(password) < 4:
        return jsonify({"error": "用户名至少2位，密码至少4位"}), 400
    try:
        user_id = User.create(username, password)
        session["user_id"] = user_id
        session["username"] = username
        return jsonify({"success": True, "user": {"id": user_id, "username": username}})
    except Exception:
        return jsonify({"error": "用户名已存在"}), 409

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    user = User.authenticate(username, password)
    if not user:
        return jsonify({"error": "用户名或密码错误"}), 401
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"success": True, "user": {"id": user["id"], "username": user["username"]}})

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    user_id = _get_current_user()
    if not user_id:
        return jsonify({"authenticated": False, "user": None})
    user = User.get_by_id(user_id)
    return jsonify({"authenticated": True, "user": {"id": user["id"], "username": user["username"]}}) if user else jsonify({"authenticated": False, "user": None})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/emails', methods=['GET'])
def get_emails():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    search = request.args.get('search', None)
    category = request.args.get('category', None)
    user_id = _get_current_user()
    result = Email.get_list(page, limit, search, category, user_id=user_id)
    return jsonify(result)

@app.route('/api/emails', methods=['POST'])
def create_email():
    data = request.get_json()
    if not data or not data.get('sender'):
        return jsonify({"error": "发件人不能为空"}), 400
    
    user_id = _get_current_user()
    email_id = Email.create(
        sender=data.get('sender', ''),
        subject=data.get('subject', ''),
        content=data.get('content', ''),
        user_id=user_id
    )
    
    producer.send_email({
        "email_id": email_id,
        "sender": data.get('sender', ''),
        "subject": data.get('subject', ''),
        "content": data.get('content', '')
    })
    
    socketio.emit('mq_event', {
        'queue': 'email_input',
        'type': 'new_email',
        'email_id': email_id,
        'subject': data.get('subject', ''),
        'mode': 'RabbitMQ' if producer.using_rabbitmq() else '内存队列'
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

@app.route('/api/emails/export', methods=['GET'])
def export_emails():
    user_id = _get_current_user()
    result = Email.get_list(1, 10000, user_id=user_id)
    emails = result.get("data", [])
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["ID", "发件人", "主题", "内容", "分类结果", "分类方法", "创建时间"])
    for e in emails:
        writer.writerow([
            e.get("id", ""),
            e.get("sender", ""),
            e.get("subject", ""),
            e.get("content", ""),
            e.get("final_category", ""),
            e.get("final_method", ""),
            e.get("created_at", "")
        ])
    output.seek(0)
    return Response(
        output.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=emails_export.csv"}
    )

@app.route('/api/emails/import', methods=['POST'])
def import_emails():
    if "file" not in request.files:
        return jsonify({"error": "请上传CSV文件"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "请选择文件"}), 400

    user_id = _get_current_user()
    try:
        content = file.read().decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        header = next(reader, None)
        imported = 0
        errors = []
        for row_num, row in enumerate(reader, start=2):
            if len(row) < 3:
                errors.append({"row": row_num, "error": "缺少列"})
                continue
            sender = (row[1] if len(row) > 1 else "").strip() or (row[0] if len(row) > 0 else "").strip()
            subject = (row[2] if len(row) > 2 else "").strip()
            body = (row[3] if len(row) > 3 else "").strip()
            if not sender:
                errors.append({"row": row_num, "error": "缺少发件人"})
                continue
            Email.create(sender, subject, body, user_id=user_id)
            imported += 1
        return jsonify({"success": True, "imported": imported, "errors": errors})
    except Exception as e:
        return jsonify({"error": f"解析失败: {str(e)}"}), 400

@app.route('/api/emails/generate', methods=['POST'])
def generate_email():
    """根据关键词生成逼真邮件"""
    data = request.get_json()
    keywords = (data.get('keywords', '') or '').strip()
    if not keywords:
        return jsonify({"error": "请输入关键词"}), 400

    generated = LLMAgent.generate_email(keywords)
    if not generated:
        return jsonify({"error": "生成失败，请先配置 LLM API Key 并启动 agent_service"}), 503

    return jsonify({
        "success": True,
        "email": generated
    })

@app.route('/api/classify/free', methods=['POST'])
def classify_email_free():
    """自由分类：LLM 自主确定类别，不限固定分类列表"""
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({"error": "邮件内容不能为空"}), 400

    user_id = _get_current_user()
    email_id = Email.create(
        sender=data.get('sender', 'unknown'),
        subject=data.get('subject', ''),
        content=data.get('content', ''),
        user_id=user_id
    )

    results = []
    for node in classifier.acceptor_nodes:
        if node.is_available():
            try:
                resp = requests.post(
                    f"{node.url}/classify-free",
                    json={"sender": data.get('sender', ''), "subject": data.get('subject', ''), "content": data.get('content', '')},
                    timeout=20
                )
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("success"):
                        r = result["result"]
                        entry = {
                            "agent_name": node.name,
                            "method": f"llm_{node.role}_free",
                            "category": r.get("category", "未分类"),
                            "confidence": r.get("confidence", 0.5),
                            "keywords": r.get("keywords", []),
                            "details": {
                                "reason": r.get("reason", ""),
                                "source": r.get("source", "llm_free"),
                                "mode": r.get("mode", "free")
                            }
                        }
                        results.append(entry)
                        Classification.create(
                            email_id=email_id, agent_name=node.name,
                            method=entry["method"], category=entry["category"],
                            confidence=entry["confidence"]
                        )
            except Exception as e:
                results.append({
                    "agent_name": node.name, "method": f"llm_{node.role}_free",
                    "category": "错误", "confidence": 0,
                    "error": str(e)
                })

    if not results:
        return jsonify({
            "success": True, "email_id": email_id,
            "final_category": "未知", "method": "llm_free",
            "agents": [], "message": "无可用 LLM 节点，请启动 agent_service 并配置 API Key"
        })

    categories = [r["category"] for r in results if r["category"] != "错误"]
    counter = Counter(categories) if categories else None

    if counter:
        final_category = counter.most_common(1)[0][0]
        consensus = f"{counter[final_category]}/{len(categories)} 一致"
    else:
        final_category = "未知"
        consensus = "无有效结果"

    FinalResult.create(email_id, final_category, "llm_free")
    return jsonify({
        "success": True, "email_id": email_id,
        "final_category": final_category, "method": "llm_free",
        "consensus": consensus, "agents": results,
        "message": f"自由分类完成: {final_category}"
    })

@app.route('/api/classify', methods=['POST'])
def classify_email():
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({"error": "邮件内容不能为空"}), 400
    
    user_id = _get_current_user()
    email_id = Email.create(
        sender=data.get('sender', 'unknown'),
        subject=data.get('subject', ''),
        content=data.get('content', ''),
        user_id=user_id
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
    
    socketio.emit('mq_event', {
        'queue': 'classification_result',
        'type': 'classification_result',
        'email_id': email_id,
        'category': result.get('final_category', ''),
        'mode': 'RabbitMQ' if producer.using_rabbitmq() else '内存队列'
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
    nodes = [a.get_stats() for a in classifier.acceptor_nodes]
    customs = [a.get_stats() for a in classifier.remote_agents]
    return jsonify({"acceptor_nodes": nodes, "custom_agents": customs})

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
    # Also refresh acceptor nodes
    node_results = []
    for node in classifier.acceptor_nodes:
        online = node.check_health()
        node_results.append({
            "url": node.url,
            "name": node.name,
            "status": node.status,
            "online": online
        })
    return jsonify({"success": True, "agents": results, "nodes": node_results})

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
        if key == 'DEEPSEEK_API_KEY':
            import os
            os.environ['DEEPSEEK_API_KEY'] = value
            for node in classifier.acceptor_nodes:
                try:
                    requests.post(f"{node.url}/health", timeout=2)
                except Exception:
                    pass
    return jsonify({"success": True})

@app.route('/api/llm/status', methods=['GET'])
def get_llm_status():
    node_statuses = []
    for node in classifier.acceptor_nodes:
        health = node.check_health()
        node_statuses.append({
            "node_id": node.id,
            "name": node.name,
            "role": node.role,
            "url": node.url,
            "status": node.status,
            "health": health
        })

    providers = LLMAgent.get_all_providers()
    active_count = sum(1 for p in providers.values() if p["active"])

    any_available = any(n["status"] == "online" for n in node_statuses)
    return jsonify({
        "available": any_available or active_count > 0,
        "total_nodes": len(node_statuses),
        "online_nodes": sum(1 for n in node_statuses if n["status"] == "online"),
        "nodes": node_statuses,
        "providers": providers,
        "active_providers": active_count,
        "total_providers": len(providers)
    })

@app.route('/api/llm/config', methods=['POST'])
def configure_llm():
    data = request.get_json()
    provider = data.get('provider', 'deepseek')
    api_key = data.get('api_key', '').strip()
    url = data.get('url', '').strip()
    model = data.get('model', '').strip()
    name = data.get('name', '').strip()

    if not api_key:
        return jsonify({"success": False, "error": "API Key 不能为空"}), 400

    import os

    if provider == "custom":
        if not url:
            return jsonify({"success": False, "error": "自定义模型需要填写 URL"}), 400
        os.environ['CUSTOM_LLM_KEY'] = api_key
        os.environ['CUSTOM_LLM_URL'] = url
        os.environ['CUSTOM_LLM_MODEL'] = model or "default-model"
        os.environ['CUSTOM_LLM_NAME'] = name or "自定义模型"
    else:
        key_mapping = {
            'deepseek': 'DEEPSEEK_API_KEY',
            'qwen': 'DASHSCOPE_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'ernie': 'ERNIE_API_KEY',
            'spark': 'SPARK_API_KEY',
            'glm': 'ZHIPU_API_KEY'
        }
        env_key = key_mapping.get(provider)
        if env_key:
            os.environ[env_key] = api_key

    results = []
    for node in classifier.acceptor_nodes:
        try:
            resp = requests.post(
                f"{node.url}/config",
                json={"api_key": api_key, "provider": provider, "url": url, "model": model},
                timeout=5
            )
            results.append({
                "node": node.name,
                "success": resp.status_code == 200,
                "message": resp.json().get("message", "") if resp.status_code == 200 else "失败"
            })
        except Exception as e:
            results.append({"node": node.name, "success": False, "message": str(e)[:80]})

    success_count = sum(1 for r in results if r["success"])
    return jsonify({
        "success": True,
        "message": f"已同步到 {success_count}/{len(results)} 个节点（重启 agent_service 后生效）",
        "results": results
    })

@app.route('/api/paxos/demo-conflict', methods=['POST'])
def paxos_demo_conflict():
    """Paxos 冲突演示：展示两阶段协议和 rejection 机制"""
    import requests as req
    nodes = [n for n in classifier.acceptor_nodes if n.is_available()]

    if len(nodes) < 3:
        return jsonify({
            "success": False,
            "error": "需要 3 个 Acceptor 节点都在线",
            "online_nodes": len(nodes)
        }), 400

    urls = [n.url for n in nodes]
    log = []
    rounds = []

    # 重置所有 acceptor
    for url in urls:
        try:
            req.post(f"{url}/paxos/reset", timeout=3)
        except Exception:
            pass

    def phase(msg):
        log.append({"type": "info", "message": msg})

    phase("【初始状态】3 个 Acceptor 的 promised_id = None，accepted_id = None")

    # 第一轮：ID=1
    phase("【第一轮】Proposer 提案 ID=1，值='会议通知'")
    r1_promises = 0
    r1_accepts = 0
    for url in urls:
        try:
            r = req.post(f"{url}/paxos/prepare", json={"proposal_id": 1, "sender": "demo"}, timeout=3)
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
                r = req.post(f"{url}/paxos/accept", json={"proposal_id": 1, "value": "会议通知", "sender": "demo"}, timeout=3)
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

    # 第二轮：ID=2（更高）
    phase("【第二轮】Proposer 提案 ID=2，值='可疑邮件' (编号更高)")
    r2_promises = 0
    r2_accepts = 0
    for url in urls:
        try:
            r = req.post(f"{url}/paxos/prepare", json={"proposal_id": 2, "sender": "demo"}, timeout=3)
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
                r = req.post(f"{url}/paxos/accept", json={"proposal_id": 2, "value": "可疑邮件", "sender": "demo"}, timeout=3)
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

    # 关键：用 ID=1 旧编号重试 → 应被拒绝
    phase("【⭐ 关键】用旧 ID=1 重新发起 Prepare → 应被拒绝！(已承诺 ID=2)")
    r3_promises = 0
    for url in urls:
        try:
            r = req.post(f"{url}/paxos/prepare", json={"proposal_id": 1, "sender": "demo"}, timeout=3)
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


@app.route('/api/queue/status', methods=['GET'])
def get_queue_status():
    return jsonify({
        "mq_available": producer.is_connected(),
        "using_rabbitmq": producer.using_rabbitmq(),
        "mode": "RabbitMQ" if producer.using_rabbitmq() else "内存队列",
        "queues": consumer.get_queue_info()
    })

@app.route('/api/queue/messages', methods=['GET'])
def get_queue_messages():
    limit = request.args.get('limit', 20, type=int)
    messages = consumer.get_recent_messages(limit)
    return jsonify({
        "mq_available": producer.is_connected(),
        "using_rabbitmq": producer.using_rabbitmq(),
        "messages": messages,
        "total": len(messages)
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    import platform
    return jsonify({
        "status": "healthy",
        "mq_available": MQ_AVAILABLE,
        "python_version": platform.python_version(),
        "agents": len(classifier.get_all_agents())
    })

@socketio.on('connect')
def handle_connect():
    print('WebSocket客户端已连接')

@socketio.on('disconnect')
def handle_disconnect():
    print('WebSocket客户端已断开')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
