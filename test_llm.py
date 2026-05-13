"""
测试脚本 - 测试整个邮件分类系统

用法:
  1. 先启动 3 个 Acceptor 节点（3 个终端窗口）:
     python agent_service.py --role security --port 8503 --id acceptor-1
     python agent_service.py --role business --port 8504 --id acceptor-2
     python agent_service.py --role general --port 8505 --id acceptor-3

  2. 再启动主应用:
     python app.py

  3. 运行测试:
     python test_llm.py
"""

import urllib.request
import json

BASE = 'http://127.0.0.1:5000'


def api(name, url, method='GET', data=None):
    try:
        req = urllib.request.Request(BASE + url, method=method)
        req.add_header('Content-Type', 'application/json')
        if data:
            req.data = json.dumps(data).encode('utf-8')
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        print(f'OK  {name}: {json.dumps(result, ensure_ascii=False)[:500]}')
        return result
    except Exception as e:
        print(f'ERR {name}: {e}')
        return None


def test_node_health(port):
    """直接测试 Acceptor 节点"""
    url = f'http://127.0.0.1:{port}'
    try:
        req = urllib.request.Request(f'{url}/health')
        resp = urllib.request.urlopen(req, timeout=3)
        result = json.loads(resp.read())
        print(f'  Node :{port} OK - {result.get("agent_role", "?")} - {result.get("agent_name", "?")}')
        return True
    except Exception as e:
        print(f'  Node :{port} ERR - {e}')
        return False


print('=== 1. 测试 Acceptor 节点连接 ===')
for port in [8503, 8504, 8505]:
    test_node_health(port)

print('\n=== 2. 查看 Agent 状态 ===')
api('Agent状态', '/api/agents/status')

print('\n=== 3. 测试分类 - 会议通知（预期: 3个Agent一致） ===')
result = api('分类', '/api/classify', 'POST', {
    "sender": "boss@company.com",
    "subject": "关于明天下午3点项目会议的通知",
    "content": "请各位同事明天下午3点准时到3楼会议室参加项目进度汇报会，请准备好各自的周报。"
})

if result and result.get('agents'):
    print('\n=== Agent 投票详情 ===')
    for a in result['agents']:
        role = f" [{a.get('role', '?')}]" if a.get('role') else ''
        source = a.get('details', {}).get('source', a.get('details', {}).get('reason', 'N/A'))
        print(f"  {a['agent_name']}{role}: {a['category']} ({(a['confidence'] * 100):.1f}%)")
        print(f"    推理: {source}")

    print(f"\n  最终结果: {result.get('final_category')}")
    print(f"  决策方式: {result.get('method')}")
    print(f"  消息: {result.get('message')}")

    if result.get('paxos_log'):
        print(f"\n  Paxos 过程 ({len(result['paxos_log'])} 步):")
        for step in result['paxos_log']:
            print(f"    [{step['type']}] {step['message']}")

print('\n=== 4. 测试分类 - 可疑邮件（可能触发 Paxos） ===')
result2 = api('分类', '/api/classify', 'POST', {
    "sender": "security@bank-secure.com",
    "subject": "您的账户需要立即验证",
    "content": "尊敬的客户，我们检测到您的银行账户存在异常交易，请立即点击以下链接验证您的身份信息，否则账户将在24小时内被冻结。"
})

if result2 and result2.get('agents'):
    print('\n=== Agent 投票详情 ===')
    for a in result2['agents']:
        role = f" [{a.get('role', '?')}]" if a.get('role') else ''
        source = a.get('details', {}).get('source', a.get('details', {}).get('reason', 'N/A'))
        print(f"  {a['agent_name']}{role}: {a['category']} ({(a['confidence'] * 100):.1f}%)")
        print(f"    推理: {source}")

    print(f"\n  最终结果: {result2.get('final_category')}")
    print(f"  决策方式: {result2.get('method')}")
    print(f"  消息: {result2.get('message')}")

    if result2.get('paxos_log'):
        print(f"\n  Paxos 过程 ({len(result2['paxos_log'])} 步):")
        for step in result2['paxos_log']:
            print(f"    [{step['type']}] {step['message']}")

print('\n=== 5. 查看 Paxos 日志 ===')
api('Paxos日志', '/api/paxos/logs?limit=5')

print('\n=== 6. 查看数据统计 ===')
api('数据统计', '/api/stats/overview')

print('\n测试完成！')
