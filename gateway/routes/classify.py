"""分类路由"""
import logging
from flask import Blueprint, request, jsonify
from infrastructure.database.models import Email, Classification, PaxosLog, FinalResult, sanitize_input
from services.classifier.classifier import classifier
from services.mapreduce.bayes import mapreduce_bayes
from infrastructure.mq.producer import producer
from infrastructure.cluster.monitor import cluster_monitor
from infrastructure.cloud_native.tracing import tracer
from gateway.middleware import login_required, rate_limit, _get_current_user

logger = logging.getLogger(__name__)
classify_bp = Blueprint('classify', __name__)

_socketio = None


def init_classify_routes(socketio):
    global _socketio
    _socketio = socketio


@classify_bp.route('/api/classify', methods=['POST'])
@login_required
@rate_limit()
def classify_email():
    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({"error": "邮件内容不能为空"}), 400

    sender = sanitize_input(data.get('sender', 'unknown'), 200)
    subject = sanitize_input(data.get('subject', ''), 500)
    content = sanitize_input(data.get('content', ''), 5000)

    # 链路追踪
    span = tracer.start_trace("classify_email", "email-classifier")
    span.set_tag("sender", sender)
    span.set_tag("subject", subject[:50])

    user_id = _get_current_user()
    email_id = Email.create(sender=sender, subject=subject, content=content, user_id=user_id)
    span.set_tag("email_id", email_id)

    # 子 Span: 消息队列
    mq_span = tracer.start_span("send_to_mq", "message-queue", span)
    producer.send_email({"email_id": email_id, "sender": sender, "subject": subject})
    if _socketio:
        _socketio.emit('mq_event', {
            'queue': 'email_input', 'type': 'new_email',
            'email_id': email_id, 'category': '',
            'mode': 'RabbitMQ' if producer.using_rabbitmq() else '内存队列'
        })
    mq_span.finish()

    # 子 Span: MapReduce 贝叶斯
    bayes_span = tracer.start_span("mapreduce_bayes", "mapreduce", span)
    bayes_category, bayes_confidence, _ = mapreduce_bayes.predict(f"{subject} {content}")
    bayes_span.set_tag("category", bayes_category)
    bayes_span.set_tag("confidence", str(bayes_confidence))
    bayes_span.finish()

    # 子 Span: Agent 分类
    agent_span = tracer.start_span("agent_classify", "llm-agents", span)
    result = classifier.classify(email_id=email_id, sender=sender, subject=subject, content=content)
    agent_span.set_tag("final_category", result.get('final_category', ''))
    agent_span.set_tag("method", result.get('final_method', ''))
    agent_span.finish()

    # 训练贝叶斯模型
    final_category = result.get('final_category', '')
    if final_category:
        mapreduce_bayes.global_model.train_single(f"{subject} {content}", final_category)

    producer.send_classification({"email_id": email_id, "result": result})

    if _socketio:
        _socketio.emit('mq_event', {
            'queue': 'classification_result', 'type': 'classification_result',
            'email_id': email_id, 'category': result.get('final_category', ''),
            'mode': 'RabbitMQ' if producer.using_rabbitmq() else '内存队列'
        })
        _socketio.emit('mq_event', {
            'queue': 'final_action', 'type': 'final_action',
            'email_id': email_id, 'category': result.get('final_category', ''), 'mode': 'saved'
        })

    # 结束追踪
    span.set_tag("final_category", result.get('final_category', ''))
    span.set_tag("final_method", result.get('final_method', ''))
    span.finish()

    # 记录指标
    cluster_monitor.record_classification()
    cluster_monitor.record_paxos_consensus(result.get('final_method', '') in ['paxos_consensus', 'majority_vote'])

    logger.info(f"Classification completed: email_id={email_id}, category={result.get('final_category', '')}")
    return jsonify(result)


@classify_bp.route('/api/classify/<int:email_id>/result', methods=['GET'])
@login_required
def get_classify_result(email_id):
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404

    classifications = Classification.get_by_email(email_id)
    final_result = FinalResult.get_by_email(email_id)
    paxos_logs = PaxosLog.get_by_email(email_id)

    return jsonify({
        "email_id": email_id, "email": email,
        "classifications": classifications, "final_result": final_result, "paxos_logs": paxos_logs
    })
