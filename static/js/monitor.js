let monitorSocket = null;

const MonitorPage = {
    cleanup() {
        if (monitorSocket) { monitorSocket.disconnect(); monitorSocket = null; }
    },

    async load() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById("page-monitor");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("monitor.title")}</h2>
                    <p class="page-subtitle">${t("monitor.subtitle")}</p>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                    <span id="ws-status" style="font-size:11px;color:#999;">WS: ${t("monitor.ws_connecting")}</span>
                    <a href="javascript:App.loadPage('settings')" class="btn btn-primary" style="text-decoration:none;">${t("monitor.llm_settings")}</a>
                    <button class="btn" type="button" onclick="MonitorPage.load()">${t("monitor.refresh")}</button>
                </div>
            </div>
            <div id="agent-overview"></div>
            <div id="agent-status"></div>
            <div id="agent-stats"></div>
        `;
        this.initSocket();
        await Promise.all([
            this.fetchOverview(),
            this.fetchAgents(),
            this.fetchAgentStats()
        ]);
    },

    initSocket() {
        if (monitorSocket) { monitorSocket.disconnect(); monitorSocket = null; }
        try {
            monitorSocket = io({ transports: ['websocket', 'polling'] });
            monitorSocket.on('connect', () => {
                const el = document.getElementById('ws-status');
                const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
                if (el) { el.textContent = 'WS: ' + t("monitor.ws_connected"); el.style.color = '#52c41a'; }
            });
            monitorSocket.on('agent_health', (data) => {
                this.updateAgentHealth(data.agents || []);
            });
            monitorSocket.on('disconnect', () => {
                const el = document.getElementById('ws-status');
                const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
                if (el) { el.textContent = 'WS: ' + t("monitor.ws_disconnected"); el.style.color = '#ff4d4f'; }
            });
        } catch (e) {
            console.error('Monitor socket init failed:', e);
        }
    },

    updateAgentHealth(agents) {
        // Update agent status cards in real-time
        const llmAgents = agents.filter(a => a.method.startsWith('llm_'));

        // Update LLM nodes section in overview
        if (llmAgents.length > 0) {
            const overviewBox = document.getElementById('agent-overview');
            if (overviewBox) {
                const nodeCards = llmAgents.map(n => {
                    const isOnline = n.status === 'online';
                    return `
                        <div style="padding:10px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <strong>${App.escape(n.name)}</strong>
                                <span style="background:${isOnline ? '#e6f7ff' : '#fff1f0'};color:${isOnline ? '#1890ff' : '#ff4d4f'};padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">${n.status}</span>
                            </div>
                            <div style="font-size:12px;color:#666;">
                                ${n.processed_count || 0} processed | ${n.avg_time_ms || 0}ms avg
                            </div>
                        </div>`;
                }).join('');

                // Only update the LLM nodes card, not the entire overview
                const llmCard = overviewBox.querySelector('.card');
                if (llmCard) {
                    const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
                    llmCard.innerHTML = `<div class="card-header"><h3>LLM Nodes <span style="font-size:11px;color:#52c41a;font-weight:normal;">${t("monitor.ws_connected")}</span></h3></div>${nodeCards}`;
                }
            }
        }
    },

    async fetchOverview() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        let llmStatus = null;
        try {
            llmStatus = await API.get('/api/llm/status');
        } catch (e) {
            console.error('Failed to fetch LLM status:', e);
        }
        const box = document.getElementById('agent-overview');
        if (!llmStatus) {
            box.innerHTML = `<div class="card"><p style="padding:12px;color:#999;">${t("common.error")}</p></div>`;
            return;
        }
        const nodeOnline = llmStatus.online_nodes || 0;
        const nodeTotal = llmStatus.total_nodes || 0;
        const providerCount = llmStatus.active_providers || 0;
        const available = llmStatus.available;

        const nodes = llmStatus.nodes || [];
        const nodeCards = nodes.map(n => {
            const isOnline = n.status === 'online';
            return `
                <div style="padding:10px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>${App.escape(n.name)}</strong>
                        <span style="background:${isOnline ? '#e6f7ff' : '#fff1f0'};color:${isOnline ? '#1890ff' : '#ff4d4f'};padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">${n.status}</span>
                        <span style="color:#999;margin-left:8px;font-size:11px;">${App.escape(n.url || '')}</span>
                    </div>
                    <div style="font-size:12px;color:#666;">
                        ${n.health ? `uptime: ${Math.round((n.health.uptime_seconds || 0) / 60)}min` : 'unreachable'}
                    </div>
                </div>`;
        }).join('');

        box.innerHTML = `
            <div class="stats-grid" style="margin-bottom:12px;">
                <div class="stat-card">
                    <div class="stat-label">${t("monitor.system_status")}</div>
                    <div class="stat-value" style="color:${available ? '#52c41a' : '#ff4d4f'};">${available ? t("monitor.online") : t("monitor.offline")}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">${t("monitor.llm_nodes")}</div>
                    <div class="stat-value">${nodeOnline}/${nodeTotal}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">${t("monitor.active_providers")}</div>
                    <div class="stat-value">${providerCount}</div>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><h3>LLM Nodes</h3></div>
                ${nodeCards || `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`}
            </div>
        `;
    },

    async fetchAgents() {
        let allAgents = [];
        try {
            const res = await API.get('/api/agents/status');
            allAgents = res.agents || [];
        } catch (e) {
            console.error('Failed to fetch agents:', e);
        }

        const llmAgents = allAgents.filter(a => a.method.startsWith('llm_'));

        let html = '<div class="card" style="margin-top:12px;"><div class="card-header"><h3>LLM Agents</h3></div>';
        if (llmAgents.length === 0) {
            html += '<p style="padding:8px 12px;color:#999;">No LLM agents online.</p>';
        }
        llmAgents.forEach(a => {
            const isOnline = a.status === 'online';
            html += `
                <div style="padding:8px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>${App.escape(a.name)}</strong>
                        <span style="background:${isOnline ? '#e6f7ff' : '#fff1f0'};color:${isOnline ? '#1890ff' : '#ff4d4f'};padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">${a.status}</span>
                    </div>
                    <div>
                        <span style="margin-left:8px;font-size:12px;color:#666;">${a.processed_count || 0} processed</span>
                        <span style="margin-left:8px;font-size:12px;color:#999;">${a.avg_time_ms || 0}ms avg</span>
                    </div>
                </div>`;
        });
        html += '</div>';
        document.getElementById('agent-status').innerHTML = html;
    },

    async fetchAgentStats() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        let stats = {};
        try { stats = await API.get('/api/agents/stats'); } catch (e) {
            console.error('Failed to fetch agent stats:', e);
        }
        let html = `<div class="card" style="margin-top:12px;"><div class="card-header"><h3>${t("monitor.classification_stats")}</h3><button class="btn btn-sm btn-danger" onclick="MonitorPage.clearStats()">${t("monitor.clear_data")}</button></div>`;
        const perf = (stats.performance || []).filter(p => p.method && p.method.startsWith('llm_'));
        if (perf.length > 0) {
            html += '<table style="width:100%;font-size:12px;border-collapse:collapse;">';
            html += '<tr style="background:#fafafa;"><th style="padding:6px 12px;text-align:left;">Agent</th><th>Method</th><th>Total</th><th>Avg Confidence</th><th>Correct</th></tr>';
            perf.forEach(p => {
                html += `<tr style="border-bottom:1px solid #f0f0f0;">
                    <td style="padding:6px 12px;">${App.escape(p.agent_name)}</td>
                    <td style="padding:6px 12px;">${App.escape(p.method)}</td>
                    <td style="padding:6px 12px;">${p.total}</td>
                    <td style="padding:6px 12px;">${((p.avg_confidence || 0) * 100).toFixed(1)}%</td>
                    <td style="padding:6px 12px;">${p.correct || 0}</td>
                </tr>`;
            });
            html += '</table>';
        } else {
            const t2 = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
            html += `<p style="padding:8px 12px;color:#999;">${t2("monitor.no_records")}</p>`;
        }
        html += '</div>';
        document.getElementById('agent-stats').innerHTML = html;
    },

    async clearStats() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!confirm(t("monitor.confirm_clear"))) return;
        try {
            const result = await API.post('/api/stats/clear');
            App.showToast(result.message || t("monitor.data_cleared"));
            await this.fetchAgentStats();
        } catch (e) {
            console.error('Failed to clear stats:', e);
            App.showToast(t("monitor.clear_failed") + ': ' + e.message, 'error');
        }
    }
};
