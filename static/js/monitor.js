const MonitorPage = {
    async load() {
        const page = document.getElementById("page-monitor");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Agent Monitor</h2>
                    <p class="page-subtitle">Agent health and message queue status.</p>
                </div>
                <button class="btn" type="button" onclick="MonitorPage.load()">Refresh</button>
            </div>
            <div id="agent-status"></div>
            <div id="agent-stats"></div>
            <div id="remote-agents"></div>
            <div id="queue-status"></div>
        `;
        await Promise.all([this.fetchAgents(), this.fetchAgentStats(), this.fetchRemoteAgents(), this.fetchQueues()]);
    },

    async fetchAgents() {
        const box = document.getElementById("agent-status");
        App.setLoading(box, "Loading agents...");
        try {
            const result = await API.get("/api/agents/status");
            const agents = result.agents || [];
            if (!agents.length) {
                box.innerHTML = `<div class="card">${App.empty("No agents")}</div>`;
                return;
            }
            box.innerHTML = `
                <div class="grid three">
                    ${agents.map((agent) => this.renderAgentCard(agent)).join("")}
                </div>
            `;
        } catch (error) {
            App.setError(box, error, () => this.fetchAgents());
        }
    },

    async fetchQueues() {
        const box = document.getElementById("queue-status");
        App.setLoading(box, "Loading queues...");
        try {
            const result = await API.get("/api/queue/status");
            const queues = result.queues || [];
            box.innerHTML = `
                <div class="card">
                    <h3 class="card-title">Message Queues</h3>
                    ${queues.length ? `
                        <div class="table-wrap">
                            <table>
                                <thead><tr><th>Queue</th><th>Messages</th><th>Consumers</th></tr></thead>
                                <tbody>${queues.map((queue) => `
                                    <tr>
                                        <td>${App.escape(queue.name || "-")}</td>
                                        <td>${App.escape(queue.messages ?? 0)}</td>
                                        <td>${App.escape(queue.consumers ?? 0)}</td>
                                    </tr>
                                `).join("")}</tbody>
                            </table>
                        </div>
                    ` : App.empty("No queue data")}
                </div>
            `;
        } catch (error) {
            App.setError(box, error, () => this.fetchQueues());
        }
    },

    async fetchAgentStats() {
        const box = document.getElementById("agent-stats");
        App.setLoading(box, "Loading agent stats...");
        try {
            const result = await API.get("/api/stats/agents");
            const stats = result.agents || [];
            box.innerHTML = `
                <div class="card">
                    <h3 class="card-title">Agent Statistics</h3>
                    ${stats.length ? `
                        <div class="table-wrap">
                            <table>
                                <thead><tr><th>Agent</th><th>Method</th><th>Total</th><th>Avg confidence</th><th>Matched final</th></tr></thead>
                                <tbody>${stats.map((item) => `
                                    <tr>
                                        <td>${App.escape(item.agent_name || "-")}</td>
                                        <td>${App.escape(item.method || "-")}</td>
                                        <td>${App.escape(item.total ?? 0)}</td>
                                        <td>${App.percent(item.avg_confidence)}</td>
                                        <td>${App.escape(item.correct ?? 0)}</td>
                                    </tr>
                                `).join("")}</tbody>
                            </table>
                        </div>
                    ` : App.empty("No agent statistics yet")}
                </div>
            `;
        } catch (error) {
            App.setError(box, error, () => this.fetchAgentStats());
        }
    },

    async fetchRemoteAgents() {
        const box = document.getElementById("remote-agents");
        App.setLoading(box, "Loading remote agents...");
        try {
            const result = await API.get("/api/agents/remote");
            const agents = result.remote_agents || [];
            box.innerHTML = `
                <div class="card">
                    <div class="section-head">
                        <h3 class="card-title">Remote Agent Management</h3>
                        <div class="toolbar compact">
                            <button class="btn btn-sm" type="button" onclick="MonitorPage.refreshRemoteAgents()">Refresh remote</button>
                            <button class="btn btn-sm btn-primary" type="button" onclick="MonitorPage.openRemoteModal()">Add remote</button>
                        </div>
                    </div>
                    ${agents.length ? `
                        <div class="grid three">
                            ${agents.map((agent) => `
                                <div class="card agent-card" style="box-shadow:none">
                                    <div class="agent-head">
                                        <strong>${App.escape(agent.name || "-")}</strong>
                                        <div class="agent-head-right">
                                            <span class="agent-kind remote">Remote</span>
                                            <span class="status-dot ${agent.status === "online" ? "online" : "offline"}"></span>
                                        </div>
                                    </div>
                                    <div>method: ${App.escape(agent.method || "-")}</div>
                                    <div class="text-muted text-truncate">${App.escape(agent.url || "-")}</div>
                                    <div>processed: ${App.escape(agent.processed_count ?? 0)}</div>
                                    <div>avg time: ${App.escape(agent.avg_time_ms ?? 0)} ms</div>
                                    <button class="btn btn-sm btn-danger" type="button" onclick="MonitorPage.removeRemoteAgent('${App.escape(agent.url || "")}')">Remove</button>
                                </div>
                            `).join("")}
                        </div>
                    ` : App.empty("No remote agents configured")}
                </div>
            `;
        } catch (error) {
            App.setError(box, error, () => this.fetchRemoteAgents());
        }
    },

    openRemoteModal() {
        App.showModal(`
            <div class="modal-header">
                <h3>Add Remote Agent</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">x</button>
            </div>
            <div class="form-grid">
                <div class="form-group"><label>Name</label><input id="remote-name" value="Remote Agent"></div>
                <div class="form-group"><label>Method</label><input id="remote-method" value="remote"></div>
                <div class="form-group"><label>URL</label><input id="remote-url" placeholder="http://127.0.0.1:5001"></div>
                <div class="form-group"><label>Timeout seconds</label><input id="remote-timeout" type="number" min="1" value="10"></div>
            </div>
            <div class="form-actions">
                <button class="btn" type="button" onclick="App.closeModal()">Cancel</button>
                <button class="btn btn-primary" type="button" onclick="MonitorPage.addRemoteAgent()">Add</button>
            </div>
        `);
    },

    async addRemoteAgent() {
        const payload = {
            name: document.getElementById("remote-name").value.trim() || "Remote Agent",
            method: document.getElementById("remote-method").value.trim() || "remote",
            url: document.getElementById("remote-url").value.trim(),
            timeout: Number(document.getElementById("remote-timeout").value || 10)
        };
        if (!payload.url) {
            App.showToast("Remote URL is required", "warning");
            return;
        }
        try {
            await API.post("/api/agents/remote", payload);
            App.closeModal();
            App.showToast("Remote agent added");
            this.fetchRemoteAgents();
            this.fetchAgents();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async refreshRemoteAgents() {
        try {
            const result = await API.post("/api/agents/remote/refresh", {});
            App.showToast(`Remote refresh complete: ${(result.agents || []).length} checked`);
            this.fetchRemoteAgents();
            this.fetchAgents();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async removeRemoteAgent(url) {
        if (!url || !confirm("Remove this remote agent?")) return;
        try {
            await API.delete("/api/agents/remote", { url });
            App.showToast("Remote agent removed");
            this.fetchRemoteAgents();
            this.fetchAgents();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    renderAgentCard(agent) {
        const kind = this.agentKind(agent);
        return `
            <div class="card agent-card">
                <div class="agent-head">
                    <strong>${App.escape(agent.name || agent.id || "-")}</strong>
                    <div class="agent-head-right">
                        <span class="agent-kind ${kind.className}">${App.escape(kind.label)}</span>
                        <span class="status-dot ${agent.status === "online" ? "online" : "offline"}"></span>
                    </div>
                </div>
                <div>method: ${App.escape(agent.method || "-")}</div>
                ${agent.role ? `<div>role: ${App.escape(agent.role)}</div>` : ""}
                ${agent.url ? `<div class="text-muted text-truncate">${App.escape(agent.url)}</div>` : ""}
                <div>processed: ${App.escape(agent.processed_count ?? 0)}</div>
                <div>avg time: ${App.escape(agent.avg_time_ms ?? 0)} ms</div>
            </div>
        `;
    },

    agentKind(agent) {
        const method = String(agent.method || "").toLowerCase();
        const role = String(agent.role || "").toLowerCase();
        if (method.includes("remote") || agent.url) {
            return { label: "Remote", className: "remote" };
        }
        if (method.includes("llm") || role) {
            return { label: "LLM Node", className: "llm" };
        }
        return { label: "Local", className: "local" };
    }
};
