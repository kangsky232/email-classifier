"""认证路由"""
import logging
from flask import Blueprint, request, jsonify, session
from infrastructure.database.models import User, sanitize_input
from gateway.middleware import rate_limit

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/register', methods=['POST'])
@rate_limit()
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求数据无效"}), 400
    username = sanitize_input(data.get("username", ""), 50)
    password = sanitize_input(data.get("password", ""), 100)
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if len(username) < 2 or len(password) < 4:
        return jsonify({"error": "用户名至少2位，密码至少4位"}), 400
    try:
        user_id = User.create(username, password)
        session["user_id"] = user_id
        session["username"] = username
        logger.info(f"New user registered: {username}")
        return jsonify({"success": True, "user": {"id": user_id, "username": username}})
    except Exception:
        return jsonify({"error": "用户名已存在"}), 409


@auth_bp.route('/api/auth/login', methods=['POST'])
@rate_limit()
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求数据无效"}), 400
    username = sanitize_input(data.get("username", ""), 50)
    password = sanitize_input(data.get("password", ""), 100)
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    user = User.authenticate(username, password)
    if not user:
        logger.warning(f"Failed login attempt for user: {username}")
        return jsonify({"error": "用户名或密码错误"}), 401
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    logger.info(f"User logged in: {username}")
    return jsonify({"success": True, "user": {"id": user["id"], "username": user["username"]}})


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})


@auth_bp.route('/api/auth/me', methods=['GET'])
def me():
    from gateway.middleware import _get_current_user
    user_id = _get_current_user()
    if not user_id:
        return jsonify({"authenticated": False, "user": None})
    user = User.get_by_id(user_id)
    return jsonify({"authenticated": True, "user": {"id": user["id"], "username": user["username"]}}) if user else jsonify({"authenticated": False, "user": None})
