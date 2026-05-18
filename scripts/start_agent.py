"""启动 Agent 节点"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.classifier.service import app

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='LLM Agent 节点服务')
    parser.add_argument('--role', type=str, default='llm1',
                        choices=['llm1', 'llm2', 'llm3', 'llm4'],
                        help='Agent 角色: llm1/llm2/llm3/llm4')
    parser.add_argument('--port', type=int, default=8503, help='服务端口')
    parser.add_argument('--id', type=str, default='acceptor-1', help='Acceptor ID')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')

    from services.classifier.llm_agent import LLMAgent
    from services.consensus.acceptor import Acceptor
    import uuid

    agent = LLMAgent(role=args.role)
    acceptor = Acceptor(args.id)
    instance_id = str(uuid.uuid4())[:6]

    # 注入到 service 模块
    import services.classifier.service as svc
    svc.agent = agent
    svc.acceptor = acceptor
    svc.instance_id = instance_id

    logger = logging.getLogger(__name__)
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
