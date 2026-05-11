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
    const onlineNodes = llmStatus.online_nodes || 0;
    const totalNodes = llmStatus.total_nodes || 3;

    document.getElementById('settings-content').innerHTML = `
        <div class="card">
            <div class="card-title">🤖 DeepSeek 大模型配置</div>
            <p style="color:#888;font-size:13px;margin-bottom:12px">
                Acceptor 节点状态: <strong>${onlineNodes}/${totalNodes}</strong> 在线
            </p>
            <div class="form-group">
                <label>DeepSeek API Key</label>
                <input type="password" id="llm-key-deepseek" class="form-control"
                       placeholder="输入 sk- 开头的 API Key..." style="width:100%">
            </div>
            <div style="display:flex;gap:8px;margin-top:8px">
                <button class="btn btn-primary" onclick="saveDeepSeekKey()">保存并同步到节点</button>
                <button class="btn" onclick="testLLM()">测试分类</button>
            </div>
            <div id="llm-save-result" style="margin-top:8px"></div>
            <div style="margin-top:12px;padding:12px;background:#f6ffed;border-radius:4px;border:1px solid #b7eb8f">
                <strong>💡 提示：</strong>输入 Key 后点击保存，会自动同步到所有 Acceptor 节点，无需重启。
            </div>
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

async function saveDeepSeekKey() {
    const apiKey = document.getElementById('llm-key-deepseek').value.trim();
    const resultDiv = document.getElementById('llm-save-result');

    if (!apiKey) {
        showToast('请输入 API Key', 'error');
        return;
    }

    resultDiv.innerHTML = '<span style="color:#1890ff">正在同步到各节点...</span>';

    try {
        const result = await fetch('/api/llm/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey })
        }).then(r => r.json());

        if (result.success) {
            let html = '<div style="color:#52c41a"><strong>Key 已同步：</strong></div><ul>';
            result.results.forEach(r => {
                html += `<li>${r.node}: ${r.success ? '✅ ' + r.message : '❌ ' + r.message}</li>`;
            });
            html += '</ul>';
            resultDiv.innerHTML = html;
            showToast('API Key 已同步到 ' + (result.results || []).filter(r => r.success).length + ' 个节点');
        } else {
            resultDiv.innerHTML = '<span style="color:#ff4d4f">保存失败</span>';
            showToast('保存失败', 'error');
        }
    } catch (e) {
        resultDiv.innerHTML = '<span style="color:#ff4d4f">请求失败: ' + e.message + '</span>';
        showToast('保存失败: ' + e.message, 'error');
    }
}

async function testLLM() {
    showToast('正在测试分类...');
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
            const apiAgents = agentResults.filter(a => a.details?.source === 'deepseek_api');
            if (apiAgents.length > 0) {
                showToast(`✅ DeepSeek 分类成功: ${apiAgents[0].category} (${(apiAgents[0].confidence*100).toFixed(1)}%)`);
            } else {
                showToast(`⚠️ 使用降级模式: ${result.final_category}`, 'warning');
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
