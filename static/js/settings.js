const SettingsPage = {
    config: {},

    async load() {
        const page = document.getElementById("page-settings");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Settings</h2>
                    <p class="page-subtitle">Manage categories, Paxos parameters, and agent settings.</p>
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
            } catch (error) {
                llmStatus = null;
            }
            this.render(llmStatus);
        } catch (error) {
            App.setError(box, error, () => this.fetchSettings());
            App.showToast(error.message, "error");
        }
    },

    render(llmStatus) {
        const box = document.getElementById("settings-content");
        const categories = Array.isArray(this.config.categories) && this.config.categories.length
            ? this.config.categories
            : ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"];
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
                    ${llmStatus ? `
                        <div>LLM nodes: <strong>${llmStatus.online_nodes || 0}/${llmStatus.total_nodes || 0}</strong> online</div>
                        <div class="text-muted">available: ${llmStatus.available ? "yes" : "no"}</div>
                    ` : '<div class="text-muted">LLM status is unavailable. Basic settings can still be saved.</div>'}
                    <div class="llm-config-box">
                        <label for="llm-api-key">DeepSeek API Key</label>
                        <input id="llm-api-key" type="password" placeholder="sk-...">
                        <button class="btn btn-sm btn-primary" type="button" onclick="SettingsPage.saveLLMKey()">Save and sync key</button>
                        <div id="llm-config-result" class="text-muted"></div>
                    </div>
                </div>
            </div>
            <div class="grid two">
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
                    <div class="form-actions">
                        <button class="btn btn-primary" type="button" onclick="SettingsPage.save()">Save Settings</button>
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

    async saveLLMKey() {
        const key = document.getElementById("llm-api-key").value.trim();
        const box = document.getElementById("llm-config-result");
        if (!key) {
            App.showToast("API Key is required", "warning");
            return;
        }
        box.textContent = "Syncing key to LLM nodes...";
        try {
            const result = await API.post("/api/llm/config", { api_key: key });
            box.innerHTML = `
                <div>${App.escape(result.message || "Saved")}</div>
                ${(result.results || []).map((item) => `
                    <div>${App.escape(item.node || "-")}: ${item.success ? "ok" : "failed"} ${App.escape(item.message || "")}</div>
                `).join("")}
            `;
            App.showToast("LLM key saved");
        } catch (error) {
            box.textContent = error.message;
            App.showToast(error.message, "error");
        }
    }
};
