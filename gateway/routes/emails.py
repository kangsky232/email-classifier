"""邮件 CRUD 路由"""
import logging
import csv
import io
import json
from flask import Blueprint, request, jsonify, Response
from infrastructure.database.models import Email, Classification, PaxosLog, FinalResult, sanitize_input
from services.classifier.llm_agent import LLMAgent
from gateway.middleware import login_required, rate_limit, _get_current_user

logger = logging.getLogger(__name__)
emails_bp = Blueprint('emails', __name__)

# 这些依赖由 gateway/app.py 注入
_gfs_master = None
_get_chunk_server = None
_producer = None
_socketio = None


def init_emails_routes(gfs_master, get_chunk_server, producer, socketio):
    global _gfs_master, _get_chunk_server, _producer, _socketio
    _gfs_master = gfs_master
    _get_chunk_server = get_chunk_server
    _producer = producer
    _socketio = socketio


@emails_bp.route('/api/emails', methods=['GET'])
@login_required
def get_emails():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    search = request.args.get('search', None)
    category = request.args.get('category', None)
    user_id = _get_current_user()
    result = Email.get_list(page, limit, search, category, user_id=user_id)
    return jsonify(result)


@emails_bp.route('/api/emails', methods=['POST'])
@login_required
@rate_limit()
def create_email():
    data = request.get_json()
    if not data or not data.get('sender'):
        return jsonify({"error": "发件人不能为空"}), 400

    sender = sanitize_input(data.get('sender', ''), 200)
    subject = sanitize_input(data.get('subject', ''), 500)
    content = sanitize_input(data.get('content', ''), 5000)

    user_id = _get_current_user()
    email_id = Email.create(sender=sender, subject=subject, content=content, user_id=user_id)

    gfs_file_id = None
    if _gfs_master:
        try:
            email_data = json.dumps({
                "sender": sender, "subject": subject, "content": content
            }, ensure_ascii=False).encode('utf-8')
            gfs_file_id = _gfs_master.create_file(
                f"emails/{email_id}.json",
                {"email_id": email_id, "type": "email"}
            )
            chunk_info = _gfs_master.allocate_chunk(gfs_file_id, 0)
            if chunk_info and _get_chunk_server:
                for server_id in chunk_info.servers:
                    server = _get_chunk_server(server_id)
                    server.write_chunk(chunk_info.chunk_id, email_data)
            logger.info(f"Email {email_id} stored in GFS: {gfs_file_id}")
        except Exception as e:
            logger.warning(f"GFS storage failed: {e}")

    if _socketio:
        _socketio.emit('email_progress', {
            'email_id': email_id,
            'stage': 'created',
            'message': f'邮件已创建，GFS存储: {"成功" if gfs_file_id else "跳过"}',
            'gfs_file_id': gfs_file_id
        })

    if _producer:
        _producer.send_email({
            "email_id": email_id, "sender": sender, "subject": subject, "content": content
        })
        _socketio.emit('mq_event', {
            'queue': 'email_input', 'type': 'new_email',
            'email_id': email_id, 'subject': subject,
            'mode': 'RabbitMQ' if _producer.using_rabbitmq() else '内存队列'
        })

    email = Email.get_by_id(email_id)
    logger.info(f"Email created: id={email_id}, sender={sender}")
    return jsonify({"success": True, "email": email, "gfs_file_id": gfs_file_id})


@emails_bp.route('/api/emails/<int:email_id>', methods=['GET'])
@login_required
def get_email(email_id):
    user_id = _get_current_user()
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    if email.get('user_id') and email['user_id'] != user_id:
        return jsonify({"error": "无权访问此邮件"}), 403

    classifications = Classification.get_by_email(email_id)
    final_result = FinalResult.get_by_email(email_id)
    paxos_logs = PaxosLog.get_by_email(email_id)

    return jsonify({
        "email": email, "classifications": classifications,
        "final_result": final_result, "paxos_logs": paxos_logs
    })


@emails_bp.route('/api/emails/<int:email_id>', methods=['PUT'])
@login_required
@rate_limit()
def update_email(email_id):
    user_id = _get_current_user()
    data = request.get_json()
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    if email.get('user_id') and email['user_id'] != user_id:
        return jsonify({"error": "无权修改此邮件"}), 403

    sender = sanitize_input(data.get('sender', email['sender']), 200)
    subject = sanitize_input(data.get('subject', email['subject']), 500)
    content = sanitize_input(data.get('content', email['content']), 5000)
    Email.update(email_id, sender=sender, subject=subject, content=content)
    logger.info(f"Email updated: id={email_id}")
    return jsonify({"success": True})


@emails_bp.route('/api/emails/<int:email_id>', methods=['DELETE'])
@login_required
@rate_limit()
def delete_email(email_id):
    user_id = _get_current_user()
    email = Email.get_by_id(email_id)
    if not email:
        return jsonify({"error": "邮件不存在"}), 404
    if email.get('user_id') and email['user_id'] != user_id:
        return jsonify({"error": "无权删除此邮件"}), 403
    Email.delete(email_id)
    logger.info(f"Email deleted: id={email_id}")
    return jsonify({"success": True})



@emails_bp.route('/api/emails/batch', methods=['POST'])
@login_required
@rate_limit()
def batch_emails():
    data = request.get_json()
    action = data.get('action')
    email_ids = data.get('email_ids', [])

    # 一键清空
    if action == 'clear_all':
        user_id = _get_current_user()
        count_result = Email.get_list(1, 1, user_id=user_id)
        total = count_result.get("total", 0)
        if total == 0:
            return jsonify({"results": [], "total": 0, "message": "没有可删除的邮件"})
        Email.delete_all(user_id)
        logger.info(f"All emails cleared by user {user_id}, count={total}")
        return jsonify({"results": [{"success": True}], "total": total, "message": f"已清空 {total} 封邮件"})

    if not email_ids:
        return jsonify({"error": "未选择邮件"}), 400

    if len(email_ids) > 1000:
        return jsonify({"error": "批量操作最多 1000 封邮件"}), 400

    from services.classifier.classifier import classifier
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
                        email_id=email_id, sender=email['sender'],
                        subject=email['subject'], content=email['content']
                    )
                    results.append({"email_id": email_id, "success": True, "result": result})
            else:
                results.append({"email_id": email_id, "success": False, "error": "未知操作"})
        except Exception as e:
            results.append({"email_id": email_id, "success": False, "error": str(e)})
    return jsonify({"results": results, "total": len(email_ids)})


@emails_bp.route('/api/emails/export', methods=['GET'])
@login_required
def export_emails():
    user_id = _get_current_user()
    result = Email.get_list(1, 10000, user_id=user_id)
    emails = result.get("data", [])
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["ID", "发件人", "主题", "内容", "分类结果", "分类方法", "创建时间"])
    for e in emails:
        writer.writerow([
            e.get("id", ""), e.get("sender", ""), e.get("subject", ""),
            e.get("content", ""), e.get("final_category", ""),
            e.get("final_method", ""), e.get("created_at", "")
        ])
    output.seek(0)
    return Response(
        output.getvalue().encode("utf-8-sig"), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=emails_export.csv"}
    )


@emails_bp.route('/api/emails/import', methods=['POST'])
@login_required
@rate_limit()
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
            Email.create(sanitize_input(sender, 200), sanitize_input(subject, 500), sanitize_input(body, 5000), user_id=user_id)
            imported += 1
        logger.info(f"CSV import completed: {imported} imported, {len(errors)} errors")
        return jsonify({"success": True, "imported": imported, "errors": errors})
    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        return jsonify({"error": f"解析失败: {str(e)}"}), 400


@emails_bp.route('/api/emails/generate', methods=['POST'])
@login_required
@rate_limit()
def generate_email():
    data = request.get_json()
    keywords = sanitize_input(data.get('keywords', ''), 200).strip()
    if not keywords:
        return jsonify({"error": "请输入关键词"}), 400
    generated = LLMAgent.generate_email(keywords)
    if not generated:
        return jsonify({"error": "生成失败，请先配置 LLM API Key 并启动 agent_service"}), 503
    return jsonify({"success": True, "email": generated})
