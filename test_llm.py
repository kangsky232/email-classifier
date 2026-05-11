import urllib.request, json

BASE = 'http://127.0.0.1:5000'

def api(name, url, method='GET', data=None):
    try:
        req = urllib.request.Request(BASE + url, method=method)
        req.add_header('Content-Type', 'application/json')
        if data:
            req.data = json.dumps(data).encode('utf-8')
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        print(f'OK  {name}: {json.dumps(result, ensure_ascii=False)[:400]}')
        return result
    except Exception as e:
        print(f'ERR {name}: {e}')
        return None

print('=== 1. 查看LLM状态 ===')
api('LLM状态', '/api/llm/status')

print('\n=== 2. 查看所有Agent状态 ===')
api('Agent状态', '/api/agents/status')

print('\n=== 3. 测试分类(无API Key, 降级模式) ===')
result = api('分类', '/api/classify', 'POST', {
    "sender": "boss@company.com",
    "subject": "明天下午3点开会",
    "content": "请各位同事明天下午3点准时到会议室参加项目进度汇报会"
})

if result and result.get('agents'):
    print('\n=== Agent投票详情 ===')
    for a in result['agents']:
        remote = ' [远程]' if a.get('is_remote') else ''
        source = a.get('details', {}).get('source', 'N/A')
        print(f"  {a['agent_name']}{remote}: {a['category']} ({(a['confidence']*100):.1f}%) [source: {source}]")

print('\n完成！')
