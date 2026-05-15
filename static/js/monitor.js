const MonitorPage = {
    async load() {
        const page = document.getElementById("page-monitor");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Agent Monitor</h2>
                    <p class="page-subtitle">Agent health and classification status.</p>
                </div>
                <button class="btn" type="button" onclick="MonitorPage.load()">Refresh</button>
            </div>
            <div id="agent-status"></div>
            <div id="agent-stats"></div>
            <div id="remote-agents"></div>
        `;
        await Promise.all([this.fetchAgents(), this.fetchAgentStats(), this.fetchRemoteAgents()]);
    },

    async fetchAgents() {
        let allAgents = [];
        try {
            const res = await $.get('/api/agents/status');
            allAgents = res.agents || [];
        } catch (e) {}

        const localAgents = allAgents.filter(a => a.method !== 'llm_security' && a.method !== 'llm_business' && a.method !== 'llm_general');

        let html = '<div class="card" style="margin-bottom:12px;"><div class="card-header"><h3>本地 Agent (ML)</h3></div>';
        if (localAgents.length === 0) {
            html += '<p style="padding:8px 12px;color:#999;">暂无本地 Agent。</p>';
        }
        localAgents.forEach(a => {
            html += `
                <div style="padding:8px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>${App.escape(a.name)}</strong>
                        <span class="agent-kind local" style="margin-left:8px;">${App.escape(a.method)}</span>
                    </div>
                    <div>
                        <span style="margin-left:8px;font-size:12px;color:#666;">${a.processed_count || 0} processed</span>
                        <span style="margin-left:8px;font-size:12px;color:#999;">${a.avg_time_ms || 0}ms avg</span>
                    </div>
                </div>`;
        });
        html += '</div>';
        document.getElementById('agent-status').innerHTML = html || '<p>No agents</p>';
    },

    async fetchAgentStats() {
        const stats = await $.get('/api/agents/stats');
        let html = '<div class="card"><div class="card-header"><h3>Agent Statistics</h3></div>';
        html += `<p style="padding:8px 12px;color:#666;">Total classified: ${stats.total_classified || 0}</p>`;
        html += '</div>';
        document.getElementById('agent-stats').innerHTML = html;
    },

    async fetchRemoteAgents() {
        let nodes = [];
        let customs = [];
        try {
            const res = await $.get('/api/agents/remote');
            nodes = res.acceptor_nodes || [];
            customs = res.custom_agents || [];
        } catch (e) {}

        let html = '<div class="card" style="margin-top:12px;"><div class="card-header"><h3>LLM 远程节点 (DeepSeek)</h3></div>';
        if (nodes.length === 0) {
            html += '<p style="padding:8px 12px;color:#999;">暂无远程节点。启动 agent_service.py 后自动检测。</p>';
        }
        nodes.forEach(a => {
            const isOnline = a.status === 'online';
            html += `
                <div style="padding:8px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>${App.escape(a.name)}</strong>
                        <span class="agent-kind llm" style="margin-left:8px">${App.escape(a.role || a.method)}</span>
                        <span style="color:#999;margin-left:8px;font-size:12px;">${App.escape(a.url || '')}</span>
                    </div>
                    <div>
                        <span style="background:${isOnline ? '#52c41a' : '#ff4d4f'};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">${a.status}</span>
                        <span style="margin-left:8px;font-size:12px;color:#666;">${a.processed_count || 0} processed</span>
                        <span style="margin-left:8px;font-size:12px;color:#999;">${a.avg_time_ms || 0}ms avg</span>
                    </div>
                </div>`;
        });
        html += '</div>';

        if (customs.length > 0) {
            html += '<div class="card" style="margin-top:12px;"><div class="card-header"><h3>自定义远程Agent</h3></div>';
            customs.forEach(a => {
                html += `
                    <div style="padding:8px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <strong>${App.escape(a.name)}</strong>
                            <span style="color:#999;margin-left:8px;">${App.escape(a.url || '')}</span>
                        </div>
                        <div>
                            <span style="background:${a.status==='online'?'#52c41a':'#ff4d4f'};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">${a.status}</span>
                            <span style="margin-left:8px;font-size:12px;color:#666;">${a.processed_count || 0} processed</span>
                        </div>
                    </div>`;
            });
            html += '</div>';
        }

        document.getElementById('remote-agents').innerHTML = html;
    }
};