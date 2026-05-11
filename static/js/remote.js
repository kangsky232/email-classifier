const RemotePage = {
    async render() {
        const page = document.getElementById('page-remote');
        page.innerHTML = `
            <div class="page-header">
                <h2>远程Agent管理</h2>
                <div class="header-actions">
                    <button class="btn btn-success" onclick="RemotePage.refreshAll()">🔄 刷新状态</button>
                    <button class="btn btn-primary" onclick="RemotePage.showAddModal()">+ 添加远程Agent</button>
                </div>
            </div>
            <div class="card" style="margin-bottom:16px; padding:12px 16px; background:#f0f7ff;">
                <strong>使用说明：</strong> 先在新终端运行 <code>python agent_service.py --type rule --port 5001</code>，然后点击"添加远程Agent"填入地址。
            </div>
            <div class="card-grid" id="remote-agents-grid">
                <div class="loading">加载中...</div>
            </div>
        `;
        await this.loadAgents();
    },

    async loadAgents() {
        try {
            const data = await API.get('/api/agents/remote');
            const grid = document.getElementById('remote-agents-grid');
            if (!data.remote_agents || data.remote_agents.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🌐</div>
                        <p>暂无远程Agent</p>
                        <p class="text-secondary">点击右上角按钮添加远程Agent服务</p>
                    </div>
                `;
                return;
            }
            const statusMap = {
                'online': { text: '在线', cls: 'success', icon: '🟢' },
                'offline': { text: '离线', cls: 'danger', icon: '🔴' },
                'checking': { text: '检测中', cls: 'warning', icon: '🟡' },
                'error': { text: '异常', cls: 'danger', icon: '🔴' }
            };
            grid.innerHTML = data.remote_agents.map(agent => {
                const st = statusMap[agent.status] || statusMap['offline'];
                return `
                <div class="card agent-card">
                    <div class="card-header">
                        <h3>${st.icon} ${agent.name}</h3>
                        <span class="badge badge-${st.cls}">${st.text}</span>
                    </div>
                    <div class="card-body">
                        <div class="info-row"><span class="label">方法:</span><span>${agent.method}</span></div>
                        <div class="info-row"><span class="label">地址:</span><span class="text-truncate">${agent.url}</span></div>
                        <div class="info-row"><span class="label">处理数:</span><span>${agent.processed_count || 0}</span></div>
                        <div class="info-row"><span class="label">平均耗时:</span><span>${agent.avg_time_ms || 0}ms</span></div>
                    </div>
                    <div class="card-footer">
                        <button class="btn btn-sm btn-info" onclick="RemotePage.testAgent('${agent.url}')">测试连接</button>
                        <button class="btn btn-sm btn-danger" onclick="RemotePage.removeAgent('${agent.url}')">移除</button>
                    </div>
                </div>`;
            }).join('');
        } catch (e) {
            App.showToast('加载远程Agent失败: ' + e.message, 'error');
        }
    },

    async refreshAll() {
        try {
            const data = await API.post('/api/agents/remote/refresh', {});
            if (data.success) {
                const online = data.agents.filter(a => a.online).length;
                App.showToast(`刷新完成: ${online}/${data.agents.length} 在线`);
                await this.loadAgents();
            }
        } catch (e) {
            App.showToast('刷新失败: ' + e.message, 'error');
        }
    },

    showAddModal() {
        App.showModal(`
            <h3>添加远程Agent</h3>
            <form id="add-remote-form" onsubmit="RemotePage.addAgent(event)">
                <div class="form-group">
                    <label>名称</label>
                    <input type="text" id="remote-name" class="form-control" placeholder="例如: 远程规则Agent" required>
                </div>
                <div class="form-group">
                    <label>分类方法</label>
                    <select id="remote-method" class="form-control">
                        <option value="remote_rule">规则引擎</option>
                        <option value="remote_bayes">朴素贝叶斯</option>
                        <option value="remote_lr">逻辑回归</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>服务地址</label>
                    <input type="text" id="remote-url" class="form-control" 
                           placeholder="http://127.0.0.1:5001" required>
                </div>
                <div class="form-group">
                    <label>超时时间(秒)</label>
                    <input type="number" id="remote-timeout" class="form-control" value="10" min="1" max="60">
                </div>
                <div class="form-actions">
                    <button type="button" class="btn" onclick="App.closeModal()">取消</button>
                    <button type="submit" class="btn btn-primary">添加</button>
                </div>
            </form>
        `);
    },

    async addAgent(e) {
        e.preventDefault();
        const name = document.getElementById('remote-name').value;
        const method = document.getElementById('remote-method').value;
        const url = document.getElementById('remote-url').value;
        const timeout = parseInt(document.getElementById('remote-timeout').value) || 10;

        try {
            const result = await API.post('/api/agents/remote', { name, method, url, timeout });
            App.closeModal();
            if (result.agent && result.agent.status === 'online') {
                App.showToast(`远程Agent添加成功，状态: 在线 ✅`, 'success');
            } else {
                App.showToast(`远程Agent已添加，但连接失败 ❌ 请确认Agent服务已启动`, 'warning');
            }
            await this.loadAgents();
        } catch (e) {
            App.showToast('添加失败: ' + e.message, 'error');
        }
    },

    async testAgent(url) {
        App.showToast('正在测试连接...');
        try {
            const resp = await fetch(url + '/health', { signal: AbortSignal.timeout(5000) });
            if (resp.ok) {
                const data = await resp.json();
                App.showToast(`✅ 连接成功! Agent: ${data.agent_type}, 实例: ${data.instance_id}, 运行: ${Math.round(data.uptime_seconds)}秒`, 'success');
            } else {
                App.showToast(`❌ 连接失败: HTTP ${resp.status}`, 'error');
            }
        } catch (e) {
            App.showToast(`❌ 连接失败: ${e.message}`, 'error');
        }
    },

    async removeAgent(url) {
        if (!confirm('确定要移除此远程Agent吗?')) return;
        try {
            await API.delete('/api/agents/remote', { url });
            App.showToast('远程Agent已移除', 'success');
            await this.loadAgents();
        } catch (e) {
            App.showToast('移除失败: ' + e.message, 'error');
        }
    }
};
