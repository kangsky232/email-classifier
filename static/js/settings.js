const SettingsPage = {
    config: {},
    providersStatus: {},

    async load() {
        const page = document.getElementById("page-settings");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Settings</h2>
                    <p class="page-subtitle">Manage categories, Paxos parameters, and AI model settings.</p>
                </div>
            </div>
            <div id="settings-content"></div>
        `;
        await this.fetchSettings();
    },

    async fetchSettings() {
        const box = document.getElementById("settings-content");
        App.setLoading(box);
        try {
            const config = await API.get("/api/config");
            this.config = config || {};
            let llmStatus = null;
            try {
                llmStatus = await API.get("/api/llm/status");
                this.providersStatus = llmStatus.providers || {};
            } catch (error) {
                llmStatus = null;
            }
            this.render(llmStatus);
        } catch (error) {
            App.setError(box, error, () => this.fetchSettings());
            App.showToast(error.message, "error");
        }
    },

    providerMeta() {
        return {
            deepseek: { name: "DeepSeek", link: "https://platform.deepseek.com", models: ["deepseek-chat", "deepseek-reasoner"] },
            qwen: { name: "通义千问", link: "https://dashscope.console.aliyun.com/apiKey", models: ["qwen-turbo", "qwen-plus", "qwen-max"] },
            openai: { name: "ChatGPT", link: "https://platform.openai.com/api-keys", models: ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"] },
            ernie: { name: "文心一言", link: "https://console.bce.baidu.com/iam/#/iam/accesslist", models: ["ERNIE-Speed-128K", "ERNIE-Bot", "ERNIE-Bot-turbo"] },
            spark: { name: "讯飞星火", link: "https://console.xfyun.cn/services/bm4", models: ["generalv3.5", "spark-lite", "spark-pro"] },
            glm: { name: "ChatGLM", link: "https://open.bigmodel.cn/usercenter/apikeys", models: ["glm-4-flash", "glm-4"] },
        };
    },

    render(llmStatus) {
        const box = document.getElementById("settings-content");
        const categories = Array.isArray(this.config.categories) && this.config.categories.length
            ? this.config.categories
            : ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"];

        const meta = this.providerMeta();
        const providers = this.providersStatus;
        const activeCount = Object.values(providers).filter(p => p.active).length;

        const providerCards = ["deepseek", "qwen", "openai", "ernie", "spark", "glm"].map(pid => {
            const m = meta[pid];
            const p = providers[pid] || { active: false, name: m.name, key_preview: "" };
            const badge = p.active
                ? '<span style="background:#52c41a;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">configured</span>'
                : '<span style="background:#d9d9d9;color:#666;padding:1px 6px;border-radius:3px;font-size:11px;">not set</span>';
            return `
                <div style="padding:10px 12px;border:1px solid #e8e8e8;border-radius:6px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <div>
                            <strong>${m.name}</strong> ${badge}
                            <span style="font-size:11px;color:#999;margin-left:6px;">${p.model || ""}</span>
                        </div>
                        <a href="${m.link}" target="_blank" style="font-size:11px;color:#1890ff;">get key -></a>
                    </div>
                    <div style="display:flex;gap:6px;">
                        <input id="llm-key-${pid}" type="password" class="form-control" style="flex:1;padding:4px 8px;font-size:12px;" placeholder="${p.key_preview || 'Enter API Key...'}">
                        <button class="btn btn-sm btn-primary" type="button" onclick="SettingsPage.saveKey('${pid}')">Save</button>
                        <button class="btn btn-sm" type="button" onclick="SettingsPage.testKey('${pid}')">Test</button>
                    </div>
                </div>`;
        }).join("");

        const customProvider = providers.custom || { active: false, name: "自定义模型", base_url: "", model: "" };
        const customBadge = customProvider.active
            ? '<span style="background:#52c41a;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">configured</span>'
            : '<span style="background:#d9d9d9;color:#666;padding:1px 6px;border-radius:3px;font-size:11px;">not set</span>';

        const nodeInfo = llmStatus
            ? `<div><span style="font-size:12px;color:#666;">LLM nodes: <strong>${llmStatus.online_nodes || 0}/${llmStatus.total_nodes || 0}</strong> online | API providers: <strong>${activeCount}</strong> configured</span></div>`
            : "";

        box.innerHTML = `
            <div class="grid two">
                <div class="card">
                    <h3 class="card-title">Categories</h3>
                    <div id="category-list" class="category-list">
                        ${categories.map((category) => this.categoryRow(category)).join("")}
                    </div>
                    <div class="form-actions">
                        <button class="btn" type="button" onclick="SettingsPage.addCategory()">Add Category</button>
                    </div>
                </div>
                <div class="card">
                    <h3 class="card-title">Runtime Status</h3>
                    ${nodeInfo}
                    <div id="llm-config-result" class="text-muted" style="margin-top:6px;font-size:12px;"></div>
                    <div class="form-actions" style="margin-top:10px;">
                        <button class="btn btn-primary" type="button" onclick="SettingsPage.save()">Save Settings</button>
                    </div>
                </div>
            </div>

            <div class="card" style="margin-top:12px;">
                <h3 class="card-title">LLM Provider Configuration</h3>
                <p style="font-size:12px;color:#888;margin-bottom:10px;">Each LLM node will try all configured providers in order. Only providers with valid API Keys will be used.</p>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 12px;">
                    <div><h4 style="margin-bottom:6px;">Built-in Providers</h4>${providerCards}</div>
                    <div>
                        <h4 style="margin-bottom:6px;">Custom Provider (OpenAI-compatible)</h4>
                        <div style="padding:10px 12px;border:1px solid #e8e8e8;border-radius:6px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                <strong>${App.escape(customProvider.name)}</strong> ${customBadge}
                            </div>
                            <div style="display:flex;flex-direction:column;gap:6px;">
                                <input id="custom-llm-name" class="form-control" style="padding:4px 8px;font-size:12px;" placeholder="Model name (e.g. MyModel)" value="${App.escape(customProvider.active ? customProvider.name : '')}">
                                <input id="custom-llm-url" class="form-control" style="padding:4px 8px;font-size:12px;" placeholder="API URL (e.g. https://api.example.com)" value="${App.escape(customProvider.active ? customProvider.base_url : '')}">
                                <input id="custom-llm-model" class="form-control" style="padding:4px 8px;font-size:12px;" placeholder="Model ID (e.g. gpt-3.5-turbo)" value="${App.escape(customProvider.active ? customProvider.model : '')}">
                                <input id="custom-llm-key" type="password" class="form-control" style="padding:4px 8px;font-size:12px;" placeholder="API Key">
                                <button class="btn btn-sm btn-primary" type="button" onclick="SettingsPage.saveKey('custom')">Save Custom Provider</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="grid two" style="margin-top:12px;">
                <div class="card">
                    <h3 class="card-title">Paxos</h3>
                    <div class="form-grid">
                        <div class="form-group"><label>Acceptor count</label><input id="paxos-acceptor-count" type="number" min="1" value="${App.escape(this.config.paxos_acceptor_count || 3)}"></div>
                        <div class="form-group"><label>Timeout (ms)</label><input id="paxos-timeout" type="number" min="100" value="${App.escape(this.config.paxos_timeout_ms || 5000)}"></div>
                        <div class="form-group"><label>Retry count</label><input id="paxos-retry" type="number" min="0" value="${App.escape(this.config.paxos_retry_count || 3)}"></div>
                    </div>
                </div>
                <div class="card">
                    <h3 class="card-title">Agents</h3>
                    <div class="form-grid">
                        <div class="form-group"><label>Minimum agent count</label><input id="agent-min-count" type="number" min="1" value="${App.escape(this.config.agent_min_count || 2)}"></div>
                    </div>
                </div>
            </div>
        `;
    },

    categoryRow(value = "") {
        return `
            <div class="category-row">
                <input class="category-input" value="${App.escape(value)}" placeholder="Category name">
                <button class="btn btn-sm btn-danger" type="button" onclick="this.parentElement.remove()">Delete</button>
            </div>
        `;
    },

    addCategory() {
        document.getElementById("category-list").insertAdjacentHTML("beforeend", this.categoryRow(""));
    },

    async save() {
        const categories = Array.from(document.querySelectorAll(".category-input"))
            .map((input) => input.value.trim())
            .filter(Boolean);
        if (!categories.length) {
            App.showToast("At least one category is required", "warning");
            return;
        }
        const payload = {
            categories,
            paxos_acceptor_count: Number(document.getElementById("paxos-acceptor-count").value || 3),
            paxos_timeout_ms: Number(document.getElementById("paxos-timeout").value || 5000),
            paxos_retry_count: Number(document.getElementById("paxos-retry").value || 3),
            agent_min_count: Number(document.getElementById("agent-min-count").value || 2)
        };
        try {
            await API.put("/api/config", payload);
            App.showToast("Settings saved");
            this.config = payload;
        } catch (error) {
            App.showToast(error.message, "error");
        }
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
            const result = await API.post("/api/llm/config", {
                provider, api_key: apiKey, url, model, name
            });
            box.innerHTML = `<span style="color:#52c41a;">${App.escape(result.message || "Saved")}</span>`;
            App.showToast("API Key saved (restart service to take effect)");
            this.fetchSettings();
        } catch (error) {
            box.textContent = error.message;
            App.showToast(error.message, "error");
        }
    },

    async testKey(provider) {
        App.showToast("Testing... creating a test classification...");
        try {
            const result = await API.post("/api/classify", {
                sender: "boss@company.com",
                subject: "明天下午3点开会",
                content: "请各位同事明天下午3点准时到会议室参加项目进度汇报会"
            });
            if (result.success) {
                const llmAgents = (result.agents || []).filter(a => a.method && a.method.startsWith("llm"));
                if (llmAgents.length > 0) {
                    const source = llmAgents[0].details?.source || "fallback";
                    if (source !== "fallback") {
                        App.showToast(`LLM works: ${llmAgents[0].category} (${(llmAgents[0].confidence * 100).toFixed(0)}%) via ${source}`);
                    } else {
                        App.showToast("LLM not connected, using fallback keyword matching", "warning");
                    }
                }
            }
        } catch (error) {
            App.showToast("Test failed: " + error.message, "error");
        }
    }
};
