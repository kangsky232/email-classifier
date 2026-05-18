const SettingsPage = {
    config: {},
    agentConfig: {},
    allProviders: {},

    async load() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById("page-settings");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("settings.title")}</h2>
                    <p class="page-subtitle">${t("settings.subtitle")}</p>
                </div>
            </div>
            <div id="settings-content"></div>
        `;
        await Promise.all([this.fetchSettings(), this.fetchAgentConfig()]);
    },

    async fetchSettings() {
        try {
            const config = await API.get("/api/config");
            this.config = config || {};
        } catch (error) {
            console.error('Failed to fetch settings:', error);
            App.showToast(error.message, "error");
        }
    },

    async fetchAgentConfig() {
        const box = document.getElementById("settings-content");
        App.setLoading(box);
        try {
            const data = await API.get("/api/llm/agent-config");
            this.agentConfig = data.agents || {};
            this.allProviders = data.providers || {};
            this.render();
        } catch (error) {
            console.error('Failed to fetch agent config:', error);
            App.setError(box, error, () => this.load());
        }
    },

    render() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById("settings-content");

        const roles = [
            { id: "llm1", label: "LLM1" },
            { id: "llm2", label: "LLM2" },
            { id: "llm3", label: "LLM3" },
            { id: "llm4", label: "LLM4" }
        ];

        box.innerHTML = `
            <div class="card">
                <h3 class="card-title">${t("settings.llm_provider")}</h3>
                <p style="color:#888;font-size:12px;margin-bottom:12px;">${t("settings.llm_desc")}</p>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
                    ${roles.map(r => this.renderAgentCard(r)).join("")}
                </div>
            </div>

            <div class="card" style="margin-top:12px;">
                <h3 class="card-title">${t("settings.api_key_config")}</h3>
                <p style="color:#888;font-size:12px;margin-bottom:12px;">${t("settings.api_key_desc")}</p>
                <div class="form-grid">
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="global-provider" onchange="SettingsPage.onGlobalProviderChange()">
                            <option value="deepseek">DeepSeek</option>
                            <option value="qwen">Qwen</option>
                            <option value="openai">ChatGPT</option>
                            <option value="ernie">ERNIE</option>
                            <option value="spark">Spark</option>
                            <option value="glm">ChatGLM</option>
                            <option value="custom">${t("settings.custom_model")}</option>
                        </select>
                    </div>
                    <div class="form-group"><label>API Key</label><input id="global-api-key" type="password" placeholder="API Key"></div>
                    <div class="form-group" id="global-url-group" style="display:none"><label>Base URL</label><input id="global-url" placeholder="https://api.example.com/v1"></div>
                    <div class="form-group" id="global-model-group" style="display:none"><label>Model</label><input id="global-model" placeholder="model-name"></div>
                </div>
                <div class="form-actions">
                    <button class="btn btn-primary" type="button" onclick="SettingsPage.saveGlobalKey()">${t("common.save")}</button>
                </div>
            </div>
        `;
    },

    renderAgentCard(role) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const cfg = this.agentConfig[role.id] || {};
        const currentProvider = cfg.provider_id || "ollama";
        const providerOptions = Object.entries(this.allProviders).map(([pid, p]) => {
            const selected = pid === currentProvider ? "selected" : "";
            return `<option value="${pid}" ${selected}>${App.escape(p.name)} (${App.escape(p.model || pid)})</option>`;
        }).join("");

        const colors = { llm1: '#2563eb', llm2: '#16a34a', llm3: '#d97706', llm4: '#7c3aed' };
        return `
            <div class="card" style="border-left:3px solid ${colors[role.id] || '#888'};">
                <div style="font-weight:700;font-size:14px;margin-bottom:10px;">${App.escape(role.label)}</div>
                <div class="form-group">
                    <label>${t("settings.llm_provider")}</label>
                    <select id="agent-provider-${role.id}" onchange="SettingsPage.onAgentProviderChange('${role.id}')">
                        <option value="ollama" ${currentProvider === 'ollama' ? 'selected' : ''}>${t("settings.ollama_local")}</option>
                        ${providerOptions}
                        <option value="custom" ${currentProvider === 'custom' ? 'selected' : ''}>${t("settings.custom_model")}</option>
                    </select>
                </div>
                <div id="agent-custom-${role.id}" style="display:${currentProvider === 'custom' ? 'block' : 'none'}">
                    <div class="form-group"><label>API Key</label><input id="agent-key-${role.id}" type="password" value="${App.escape(cfg.api_key || '')}" placeholder="API Key"></div>
                    <div class="form-group"><label>Base URL</label><input id="agent-url-${role.id}" value="${App.escape(cfg.base_url || '')}" placeholder="https://api.example.com/v1"></div>
                    <div class="form-group"><label>Model</label><input id="agent-model-${role.id}" value="${App.escape(cfg.model || '')}" placeholder="model-name"></div>
                    <div class="form-group"><label>Display Name</label><input id="agent-name-${role.id}" value="${App.escape(cfg.custom_name || '')}" placeholder="My Model"></div>
                </div>
                <div class="form-actions">
                    <button class="btn btn-sm btn-primary" type="button" onclick="SettingsPage.saveAgentConfig('${role.id}')">${t("common.save")}</button>
                </div>
            </div>
        `;
    },

    onAgentProviderChange(role) {
        const val = document.getElementById(`agent-provider-${role}`).value;
        const customDiv = document.getElementById(`agent-custom-${role}`);
        if (customDiv) customDiv.style.display = val === "custom" ? "block" : "none";
    },

    onGlobalProviderChange() {
        const val = document.getElementById("global-provider").value;
        document.getElementById("global-url-group").style.display = val === "custom" ? "block" : "none";
        document.getElementById("global-model-group").style.display = val === "custom" ? "block" : "none";
    },

    async saveAgentConfig(role) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const providerId = document.getElementById(`agent-provider-${role}`).value;
        const payload = { role, provider_id: providerId };

        if (providerId === "custom") {
            payload.api_key = document.getElementById(`agent-key-${role}`).value.trim();
            payload.base_url = document.getElementById(`agent-url-${role}`).value.trim();
            payload.model = document.getElementById(`agent-model-${role}`).value.trim();
            payload.custom_name = document.getElementById(`agent-name-${role}`).value.trim();
            if (!payload.api_key || !payload.base_url) {
                App.showToast(t("settings.custom_requires"), "warning");
                return;
            }
        } else if (providerId !== "ollama") {
            const p = this.allProviders[providerId];
            if (p && p.env_key) {
                const keyInput = document.getElementById(`agent-key-${role}`);
                if (keyInput) payload.api_key = keyInput.value.trim();
            }
        }

        try {
            const result = await API.post("/api/llm/agent-config", payload);
            App.showToast(result.message || t("settings.save_success"));
            await this.fetchAgentConfig();
        } catch (error) {
            console.error('Failed to save agent config:', error);
            App.showToast(error.message, "error");
        }
    },

    async saveGlobalKey() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const provider = document.getElementById("global-provider").value;
        const apiKey = document.getElementById("global-api-key").value.trim();
        if (!apiKey) {
            App.showToast("API Key " + t("common.error"), "warning");
            return;
        }
        const payload = { provider, api_key: apiKey };
        if (provider === "custom") {
            payload.url = document.getElementById("global-url").value.trim();
            payload.model = document.getElementById("global-model").value.trim();
            if (!payload.url) {
                App.showToast(t("settings.custom_requires"), "warning");
                return;
            }
        }
        try {
            const result = await API.post("/api/llm/config", payload);
            App.showToast(result.message || t("settings.save_success"));
        } catch (error) {
            console.error('Failed to save global key:', error);
            App.showToast(error.message, "error");
        }
    }
};
