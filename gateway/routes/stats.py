"""统计路由"""
import logging
from flask import Blueprint, request, jsonify
from infrastructure.database.models import FinalResult, Classification, PaxosLog, Email, SystemConfig
from services.classifier.classifier import classifier
from gateway.middleware import login_required, rate_limit, _get_current_user

logger = logging.getLogger(__name__)
stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/overview', methods=['GET'])
@login_required
def get_stats_overview():
    stats = FinalResult.get_stats()
    return jsonify(stats)


@stats_bp.route('/api/stats/categories', methods=['GET'])
@login_required
def get_stats_categories():
    stats = FinalResult.get_stats()
    return jsonify({"categories": stats.get("categories", [])})


@stats_bp.route('/api/stats/trends', methods=['GET'])
@login_required
def get_stats_trends():
    stats = FinalResult.get_stats()
    return jsonify({"trends": stats.get("trends", [])})


@stats_bp.route('/api/stats/agents', methods=['GET'])
@login_required
def get_stats_agents():
    stats = Classification.get_agent_stats()
    return jsonify({"agents": stats})


@stats_bp.route('/api/stats/clear', methods=['POST'])
@login_required
def clear_stats():
    try:
        from infrastructure.database.db import db
        user_id = _get_current_user()
        # 只清空当前用户邮件的分类统计，不影响其他用户
        email_ids = db.fetch_all("SELECT id FROM emails WHERE user_id = %s", (user_id,))
        email_ids = [r["id"] for r in email_ids]
        if email_ids:
            placeholders = ",".join(["%s"] * len(email_ids))
            db.execute(f"DELETE FROM classifications WHERE email_id IN ({placeholders})", email_ids)
            db.execute(f"DELETE FROM final_results WHERE email_id IN ({placeholders})", email_ids)
            db.execute(f"DELETE FROM paxos_logs WHERE email_id IN ({placeholders})", email_ids)
        logger.info(f"Stats cleared by user {user_id}, {len(email_ids)} emails affected")
        return jsonify({"success": True, "message": f"分类统计数据已清空（{len(email_ids)} 封邮件）"})
    except Exception as e:
        logger.error(f"Failed to clear stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@stats_bp.route('/api/agents/status', methods=['GET'])
@login_required
def get_agents_status():
    status = classifier.get_agents_status()
    return jsonify({"agents": status})


@stats_bp.route('/api/agents/stats', methods=['GET'])
@login_required
def get_agents_stats():
    stats = classifier.get_agents_stats()
    return jsonify(stats)




@stats_bp.route('/api/paxos/logs', methods=['GET'])
@login_required
def get_paxos_logs():
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 500)
    email_id = request.args.get('email_id', None, type=int)
    result = PaxosLog.get_list(page, limit, email_id)
    return jsonify(result)


@stats_bp.route('/api/paxos/logs/<int:email_id>', methods=['GET'])
@login_required
def get_paxos_logs_by_email(email_id):
    logs = PaxosLog.get_by_email(email_id)
    return jsonify({"email_id": email_id, "logs": logs})
