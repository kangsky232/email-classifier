"""启动 API 网关"""
import sys
import os

# 确保 v2 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.app import app, socketio

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='启动 API 网关')
    parser.add_argument('--port', type=int, default=5000, help='端口号')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    parser.add_argument('--prod', action='store_true', help='生产模式')
    args = parser.parse_args()

    if args.prod:
        import eventlet
        eventlet.monkey_patch()
        socketio.run(app, host=args.host, port=args.port, debug=False)
    else:
        socketio.run(app, host=args.host, port=args.port, debug=True, allow_unsafe_werkzeug=True)
