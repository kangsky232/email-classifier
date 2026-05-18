"""中间件：限流、认证等"""
import functools
import time
import threading
from collections import defaultdict
from flask import request, jsonify, session


# ============================================
# Rate Limiter
# ============================================
_rate_limits = defaultdict(list)
_rate_limit_lock = threading.Lock()


def rate_limit(max_requests=60, window=60):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            with _rate_limit_lock:
                _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < window]
                if len(_rate_limits[ip]) >= max_requests:
                    return jsonify({"error": "请求过于频繁，请稍后再试"}), 429
                _rate_limits[ip].append(now)
                # 定期清理过期 IP（每 100 次请求清理一次）
                if len(_rate_limits) > 1000:
                    expired = [k for k, v in _rate_limits.items() if not v or now - v[-1] > window]
                    for k in expired:
                        del _rate_limits[k]
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ============================================
# Auth Helpers
# ============================================
def _get_current_user():
    if "user_id" in session:
        return session.get("user_id")
    return None


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = _get_current_user()
        if not user_id:
            return jsonify({"error": "请先登录", "code": 401}), 401
        return f(*args, **kwargs)
    return decorated
