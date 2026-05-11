async function loadSettingsPage() {
    const container = document.getElementById('page-settings');
    container.innerHTML = `
        <div class="page-header"><h1>⚙️ 系统设置</h1></div>
        <div id="settings-content"><div class="loading">加载中...</div></div>
    `;
    fetchSettings();
}

async function fetchSettings() {
    const data = await api('/api/config');
    const llmData = await api('/api/llm/status');
    if (!data) return;
    
    const categories = data.categories || ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"];
    const acceptorCount = data.paxos_acceptor_count || 3;
    const timeout = data.paxos_timeout_ms || 5000;
    const retryCount = data.paxos_retry_count || 3;
    const agentMin = data.agent_min_count || 2;
    
    let categoryItems = categories.map((c, i) => `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
            <input type="text" class="category-input" value="${c}" style="flex:1">
            <button class="btn btn-sm btn-danger" onclick="removeCategory(${i})">删除</button>
        </div>
    `).join('');
    
    const llmStatus = llmData || {};
    const providers = llmStatus.providers || {};
    const availableList = llmStatus.available_list || [];
    
    const providerNames = {
        'qwen': '通义千问',
        'openai': 'ChatGPT',
        'ernie': '文心一言',
        'spark': '讯飞星火',
        'glm': 'ChatGLM'
    };
    const providerLinks = {
        'qwen': 'https://dashscope.console.aliyun.com/apiKey',
        'openai': 'https://platform.openai.com/api-keys',
        'ernie': 'https://console.bce.baidu.com/iam/#/iam/accesslist',
        'spark': 'https://console.xfyun.cn/services/bm4',
        'glm': 'https://open.bigmodel.cn/usercenter/apikeys'
    };
    const providerModels = {
        'qwen': ['qwen-turbo', 'qwen-plus', 'qwen-max'],
        'openai': ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo'],
        'ernie': ['ernie-bot', 'ernie-bot-turbo'],
        'spark': ['spark-lite', 'spark-pro'],
        'glm': ['glm-4-flash', 'glm-4']
    };
    
    let providerCards = Object.entries(providerNames).map(([key, name]) => {
        const p = providers[key] || {};
        const isActive = p.active || false;
        const statusBadge = isActive 
            ? '<span class="badge badge-success">已配置</span>' 
            : '<span class="badge badge-secondary">未配置</span>';
        const models = providerModels[key] || [];
        const modelOptions = models.map(m => `<option value="${m}">${m}</option>`).join('');
        
        return `
            <div class="card" style="margin-bottom:12px;border-left:3px solid ${isActive ? '#52c41a' : '#d9d9d9'}">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <strong>${name} ${statusBadge}</strong>
                    <a href="${providerLinks[key]}" target="_blank" style="color:#1890ff;font-size:12px">获取API Key →</a>
                </div>
                <div class="form-group" style="margin-top:8px">
                    <input type="password" id="llm-key-${key}" class="form-control" 
                           placeholder="${p.key_preview || '输入 API Key...'}" value="">
                </div>
                <div style="display:flex;gap:8px;align-items:center">
                    <button class="btn btn-sm btn-primary" onclick="saveProviderKey('${key}')">保存</button>
                    <button class="btn btn-sm" onclick="testProviderKey('${key}')">测试</button>
                </div>
            </div>
        `;
    }).join('');

    document.getElementById('settings-content').innerHTML = `
        <div class="card">
            <div class="card-title">🤖 多模型大模型配置</div>
            <p style="color:#888;font-size:13px;margin-bottom:12px">
                已配置 <strong>${availableList.length}</strong> 个模型，共支持 5 种大模型 API。在 <code>.env</code> 文件中配置 API Key。
            </p>
            <div id="llm-providers">${providerCards}</div>
            <div style="margin-top:12px;padding:12px;background:#f6ffed;border-radius:4px;border:1px solid #b7eb8f">
                <strong>💡 提示：</strong>在项目根目录的 <code>.env</code> 文件中填写 API Key，重启服务后生效。
                也可以在上方直接输入并保存（仅当次运行有效）。
            </div>
            <button class="btn" onclick="testLLM()" style="margin-top:12px">🎯 测试邮件分类（多模型）</button>
        </div>
        <div class="card">
            <div class="card-title">分类类别管理</div>
            <div id="category-list">${categoryItems}</div>
            <button class="btn btn-sm btn-success" onclick="addCategory()" style="margin-top:8px">+ 添加类别</button>
        </div>
        <div class="card">
            <div class="card-title">Paxos参数配置</div>
            <div class="form-group">
                <label>Acceptor数量</label>
                <input type="number" id="setting-acceptor" value="${acceptorCount}" min="1" max="9">
            </div>
            <div class="form-group">
                <label>超时时间 (ms)</label>
                <input type="number" id="setting-timeout" value="${timeout}">
            </div>
            <div class="form-group">
                <label>重试次数</label>
                <input type="number" id="setting-retry" value="${retryCount}">
            </div>
        </div>
        <div class="card">
            <div class="card-title">Agent配置</div>
            <div class="form-group">
                <label>最少Agent数</label>
                <input type="number" id="setting-agent-min" value="${agentMin}" min="1" max="3">
            </div>
        </div>
        <div class="btn-group">
            <button class="btn btn-primary" onclick="saveSettings()">保存设置</button>
        </div>
    `;
}

async function saveProviderKey(provider) {
    const apiKey = document.getElementById(`llm-key-${provider}`).value.trim();
    
    if (!apiKey) {
        showToast('请输入API Key', 'error');
        return;
    }
    
    try {
        const result = await fetch('/api/llm/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider, api_key: apiKey })
        }).then(r => r.json());
        
        if (result.success) {
            showToast(`${provider} API Key保存成功`);
            fetchSettings();
        }
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

async function testProviderKey(provider) {
    showToast(`正在测试 ${provider} 模型...`);
    try {
        const result = await fetch('/api/classify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sender: 'boss@company.com',
                subject: '明天下午3点开会',
                content: '请各位同事明天下午3点准时到会议室参加项目进度汇报会'
            })
        }).then(r => r.json());
        
        if (result.success) {
            const llmAgent = result.agents.find(a => a.method === 'llm');
            if (llmAgent) {
                const source = llmAgent.details?.source || 'unknown';
                if (source !== 'fallback') {
                    showToast(`✅ 分类成功: ${llmAgent.category} (${(llmAgent.confidence*100).toFixed(1)}%) - 模型: ${source}`);
                } else {
                    showToast(`⚠️ 模型未连接，使用降级方案: ${llmAgent.category}`, 'warning');
                }
            }
        }
    } catch (e) {
        showToast('测试失败: ' + e.message, 'error');
    }
}

async function saveLLMConfig() {
    showToast('请直接在上方保存各模型的API Key');
}

async function testLLM() {
    showToast('正在测试多模型分类...');
    try {
        const result = await fetch('/api/classify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sender: 'boss@company.com',
                subject: '明天下午3点开会',
                content: '请各位同事明天下午3点准时到会议室参加项目进度汇报会'
            })
        }).then(r => r.json());
        
        if (result.success) {
            const agentResults = result.agents || [];
            const llmAgents = agentResults.filter(a => a.method === 'llm');
            if (llmAgents.length > 0) {
                const source = llmAgents[0].details?.source || 'unknown';
                if (source !== 'fallback') {
                    showToast(`✅ 分类成功: ${llmAgents[0].category} (${(llmAgents[0].confidence*100).toFixed(1)}%) - 来源: ${source}`);
                } else {
                    showToast(`⚠️ 所有大模型未配置，使用降级方案: ${llmAgents[0].category}`, 'warning');
                }
            } else {
                showToast(`分类完成: ${result.final_category}`);
            }
        }
    } catch (e) {
        showToast('测试失败: ' + e.message, 'error');
    }
}

function addCategory() {
    const list = document.getElementById('category-list');
    const div = document.createElement('div');
    div.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px';
    div.innerHTML = `
        <input type="text" class="category-input" value="新类别" style="flex:1">
        <button class="btn btn-sm btn-danger" onclick="this.parentElement.remove()">删除</button>
    `;
    list.appendChild(div);
}

function removeCategory(index) {
    const inputs = document.querySelectorAll('.category-input');
    if (inputs.length <= 1) { showToast('至少保留一个类别', 'error'); return; }
    inputs[index].parentElement.remove();
}

async function saveSettings() {
    const categories = Array.from(document.querySelectorAll('.category-input')).map(i => i.value).filter(v => v);
    
    const config = {
        categories: categories,
        paxos_acceptor_count: parseInt(document.getElementById('setting-acceptor').value),
        paxos_timeout_ms: parseInt(document.getElementById('setting-timeout').value),
        paxos_retry_count: parseInt(document.getElementById('setting-retry').value),
        agent_min_count: parseInt(document.getElementById('setting-agent-min').value)
    };
    
    try {
        const result = await fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        }).then(r => r.json());
        
        if (result && result.success) {
            showToast('设置保存成功');
        }
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}
