from flask import Flask, request, jsonify
from flask_cors import CORS
from agents.rule_agent import RuleAgent
from agents.bayes_agent import BayesAgent
from agents.lr_agent import LRAgent
import argparse
import time
import uuid

app = Flask(__name__)
CORS(app)

AGENT_MAP = {
    "rule": lambda: RuleAgent(),
    "bayes": lambda: BayesAgent(),
    "lr": lambda: LRAgent()
}

agent_instance = None
agent_type = None
instance_id = str(uuid.uuid4())[:6]
start_time = time.time()
request_count = 0

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "agent_type": agent_type,
        "instance_id": instance_id,
        "uptime_seconds": round(time.time() - start_time, 2),
        "request_count": request_count
    })

@app.route('/classify', methods=['POST'])
def classify():
    global request_count
    request_count += 1
    
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({"error": "邮件内容不能为空"}), 400
    
    sender = data.get('sender', '')
    subject = data.get('subject', '')
    content = data.get('content', '')
    
    try:
        result = agent_instance.classify(sender, subject, content)
        return jsonify({
            "success": True,
            "agent_name": agent_instance.name,
            "agent_method": agent_instance.method,
            "instance_id": instance_id,
            "result": result
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "agent_name": agent_instance.name,
            "error": str(e)
        }), 500

@app.route('/stats', methods=['GET'])
def stats():
    return jsonify({
        "agent": agent_instance.get_stats(),
        "instance_id": instance_id,
        "uptime_seconds": round(time.time() - start_time, 2),
        "request_count": request_count
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='独立Agent分类服务')
    parser.add_argument('--type', type=str, default='rule', choices=['rule', 'bayes', 'lr'], help='Agent类型')
    parser.add_argument('--port', type=int, default=5001, help='服务端口')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    args = parser.parse_args()
    
    agent_type = args.type
    agent_instance = AGENT_MAP[agent_type]()
    
    print(f"启动Agent服务: {agent_instance.name} ({agent_instance.method})")
    print(f"实例ID: {instance_id}")
    print(f"监听地址: {args.host}:{args.port}")
    
    app.run(debug=False, host=args.host, port=args.port)
