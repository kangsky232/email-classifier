const MonitorPage = {
    llmData: null,
    providerMeta: {
        deepseek: { name: "DeepSeek", link: "https://platform.deepseek.com" },
        qwen: { name: "通义千问", link: "https://dashscope.console.aliyun.com/apiKey" },
        openai: { name: "ChatGPT", link: "https://platform.openai.com/api-keys" },
        ernie: { name: "文心一言", link: "https://console.bce.baidu.com/iam/#/iam/accesslist" },
        spark: { name: "讯飞星火", link: "https://console.xfyun.cn/services/bm4" },
        glm: { name: "ChatGLM", link: "https://open.bigmodel.cn/usercenter/apikeys" },
    },

    async load() {
        const page = document.getElementById("page-monitor");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Agent Monitor</h2>
                    <p class="page-subtitle">Agent health, LLM configuration, and classification status.</p>
                </div>
                <button class="btn" type="button" onclick="MonitorPage.load()">Refresh</button>
            </div>
            <div id="agent-status"></div>
            <div id="agent-stats"></div>
            <div id="remote-agents"></div>
            <div id="llm-config"></div>
        `;
        await Promise.all([
            this.fetchAgents(),
            this.fetchAgentStats(),
            this.fetchRemoteAgents(),
            this.fetchLLMConfig()
        ]);
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
        let stats = {};
        try { stats = await $.get('/api/agents/stats'); } catch (e) {}
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
    },

    async fetchLLMConfig() {
        let llmStatus = null;
        try {
            llmStatus = await $.get('/api/llm/status');
        } catch (e) {}

        const providers = llmStatus ? llmStatus.providers || {} : {};
        const activeCount = Object.values(providers).filter(p => p.active).length;
        const nodeOnline = llmStatus ? `${llmStatus.online_nodes || 0}/${llmStatus.total_nodes || 0}` : "0/0";

        const providerCards = ["deepseek", "qwen", "openai", "ernie", "spark", "glm"].map(pid => {
            const m = this.providerMeta[pid];
            const p = providers[pid] || { active: false, name: m.name, key_preview: "", model: "" };
            const badge = p.active
                ? '<span style="background:#52c41a;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">configured</span>'
                : '<span style="background:#d9d9d9;color:#666;padding:1px 6px;border-radius:3px;font-size:11px;">not set</span>';
            return `
                <div style="padding:8px 10px;border:1px solid #e8e8e8;border-radius:6px;margin-bottom:6px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <div>
                            <strong>${m.name}</strong> ${badge}
                            <span style="font-size:11px;color:#999;margin-left:6px;">${p.model || ""}</span>
                        </div>
                        <a href="${m.link}" target="_blank" style="font-size:11px;color:#1890ff;">get key</a>
                    </div>
                    <div style="display:flex;gap:4px;">
                        <input id="llm-key-${pid}" type="password" style="flex:1;padding:3px 6px;font-size:11px;border:1px solid #d9d9d9;border-radius:4px;" placeholder="${p.key_preview || 'API Key...'}">
                        <button class="btn btn-sm btn-primary" type="button" onclick="MonitorPage.saveKey('${pid}')" style="padding:3px 8px;font-size:11px;">Save</button>
                    </div>
                </div>`;
        }).join("");

        const customProvider = providers.custom || { active: false, name: "自定义模型", base_url: "", model: "" };
        const customBadge = customProvider.active
            ? '<span style="background:#52c41a;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">configured</span>'
            : '<span style="background:#d9d9d9;color:#666;padding:1px 6px;border-radius:3px;font-size:11px;">not set</span>';

        let html = '<div class="card" style="margin-top:12px;">';
        html += `<div class="card-header"><h3>LLM Provider 配置</h3><span style="font-size:12px;color:#888;">节点: ${nodeOnline} online | Providers: ${activeCount} configured</span></div>`;
        html += '<p style="padding:4px 12px;font-size:11px;color:#888;">各节点按顺序尝试已配置的 Provider，第一个成功即返回。无 Key 时自动降级为关键词匹配。</p>';

        html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:0 12px;padding:0 12px 12px;">`;
        html += `<div><h4 style="font-size:13px;margin:8px 0 6px;">Built-in</h4>${providerCards}</div>`;
        html += `
            <div>
                <h4 style="font-size:13px;margin:8px 0 6px;">Custom (OpenAI-compat)</h4>
                <div style="padding:8px 10px;border:1px solid #e8e8e8;border-radius:6px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <strong style="font-size:12px;">${App.escape(customProvider.name)}</strong> ${customBadge}
                    </div>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        <input id="custom-llm-name" style="padding:3px 6px;font-size:11px;border:1px solid #d9d9d9;border-radius:4px;" placeholder="Name (e.g. MyModel)" value="${App.escape(customProvider.active ? customProvider.name : '')}">
                        <input id="custom-llm-url" style="padding:3px 6px;font-size:11px;border:1px solid #d9d9d9;border-radius:4px;" placeholder="API URL (e.g. https://api.example.com)" value="${App.escape(customProvider.active ? customProvider.base_url : '')}">
                        <input id="custom-llm-model" style="padding:3px 6px;font-size:11px;border:1px solid #d9d9d9;border-radius:4px;" placeholder="Model ID (e.g. gpt-3.5-turbo)" value="${App.escape(customProvider.active ? customProvider.model : '')}">
                        <input id="custom-llm-key" type="password" style="padding:3px 6px;font-size:11px;border:1px solid #d9d9d9;border-radius:4px;" placeholder="API Key">
                        <button class="btn btn-sm btn-primary" type="button" onclick="MonitorPage.saveKey('custom')" style="padding:3px 8px;font-size:11px;">Save</button>
                    </div>
                </div>
            </div>`;
        html += `</div>`;
        html += '<div id="llm-config-result" style="padding:4px 12px 8px;font-size:11px;color:#52c41a;"></div>';
        html += '</div>';

        document.getElementById('llm-config').innerHTML = html;
        this.llmData = llmStatus;
    },

    async saveKey(provider) {
        let apiKey, url, model, name;
        if (provider === "custom") {
            apiKey = document.getElementById("custom-llm-key").value.trim();
            url = document.getElementById("custom-llm-url").value.trim();
            model = document.getElementById("custom-llm-model").value.trim();
            name = document.getElementById("custom-llm-name").value.trim();
        } else {
            apiKey = document.getElementById(`llm-key-${provider}`).value.trim();
        }

        if (!apiKey) {
            App.showToast("API Key is required", "warning");
            return;
        }
        if (provider === "custom" && !url) {
            App.showToast("Custom model requires a URL", "warning");
            return;
        }

        const box = document.getElementById("llm-config-result");
        box.textContent = "Saving...";
        try {
            const result = await $.post('/api/llm/config', {
                provider, api_key: apiKey, url, model, name
            });
            box.textContent = (result.message || "Saved") + " (restart agent_service to take effect)";
            App.showToast("API Key saved");
            this.fetchLLMConfig();
        } catch (e) {
            box.innerHTML = `<span style="color:#ff4d4f;">${App.escape(e.message)}</span>`;
            App.showToast(e.message, "error");
        }
    }
};
