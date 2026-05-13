const ClassifyPage = {
    load() {
        const page = document.getElementById("page-classify");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Classify Center</h2>
                    <p class="page-subtitle">Submit email content to the existing /api/classify endpoint.</p>
                </div>
            </div>
            <div class="grid two">
                <div class="card">
                    <h3 class="card-title">Input</h3>
                    <div class="form-grid">
                        <div class="form-group"><label>Sender</label><input id="classify-sender" value="boss@company.com"></div>
                        <div class="form-group"><label>Subject</label><input id="classify-subject" value="Project meeting notice"></div>
                        <div class="form-group"><label>Content</label><textarea id="classify-content">Please attend the project progress meeting tomorrow at 3 PM.</textarea></div>
                    </div>
                    <div class="form-actions">
                        <button class="btn" type="button" onclick="ClassifyPage.clear()">Clear</button>
                        <button id="classify-submit" class="btn btn-primary" type="button" onclick="ClassifyPage.submit()">Submit</button>
                    </div>
                </div>
                <div id="classify-result" class="card">
                    <h3 class="card-title">Result</h3>
                    <div class="empty-state">Submit an email to see final category, agent votes, and Paxos logs.</div>
                </div>
            </div>
        `;
    },

    clear() {
        document.getElementById("classify-sender").value = "";
        document.getElementById("classify-subject").value = "";
        document.getElementById("classify-content").value = "";
        document.getElementById("classify-result").innerHTML = `
            <h3 class="card-title">Result</h3>
            <div class="empty-state">Submit an email to see final category, agent votes, and Paxos logs.</div>
        `;
    },

    async submit() {
        const sender = document.getElementById("classify-sender").value.trim() || "unknown";
        const subject = document.getElementById("classify-subject").value.trim();
        const content = document.getElementById("classify-content").value.trim();
        const button = document.getElementById("classify-submit");
        const box = document.getElementById("classify-result");
        if (!content) {
            App.showToast("Content is required", "warning");
            return;
        }
        button.disabled = true;
        App.setLoading(box, "Classifying...");
        try {
            const result = await API.post("/api/classify", { sender, subject, content });
            this.renderResult(result);
            App.showToast("Classification complete");
        } catch (error) {
            App.setError(box, error, () => this.submit());
            App.showToast(error.message, "error");
        } finally {
            button.disabled = false;
        }
    },

    renderResult(result) {
        const box = document.getElementById("classify-result");
        if (!result.success) {
            App.setError(box, result.message || "Classification failed");
            return;
        }
        const agents = result.agents || [];
        const paxosLog = result.paxos_log || [];
        box.innerHTML = `
            <h3 class="card-title">Result</h3>
            <div class="result-hero">
                <div class="completion-animation" aria-label="Classification completed">
                    <div class="completion-ring">
                        <span class="completion-check">✓</span>
                    </div>
                    <div class="completion-pulse"></div>
                </div>
                <div>
                    <div class="stat-label">Final category</div>
                    <div class="stat-value">${App.escape(result.final_category || "-")}</div>
                </div>
                <div class="text-muted">method: ${App.escape(result.method || "-")} ${result.email_id ? `| email id: ${result.email_id}` : ""}</div>
                ${result.message ? `<p>${App.escape(result.message)}</p>` : ""}
            </div>
            <h4>Agent Results</h4>
            ${this.renderAgents(agents)}
            <h4>Paxos Process</h4>
            ${this.renderPaxos(paxosLog)}
        `;
    },

    renderAgents(agents) {
        if (!agents.length) return App.empty("No agent results");
        return `
            <div class="agent-result-grid">
                ${agents.map((agent, index) => {
                    const confidence = Number(agent.confidence) || 0;
                    const safeConfidence = Math.max(0, Math.min(confidence, 1));
                    const category = agent.category || "Unknown";
                    const color = this.categoryColor(category, index);
                    return `
                        <div class="card agent-card agent-result-card" style="box-shadow:none">
                            <div class="agent-head">
                                <strong>${App.escape(agent.agent_name || agent.name || "-")}</strong>
                                ${App.badge(agent.category)}
                            </div>
                            <div class="text-muted">${App.escape(agent.method || "-")}</div>
                            <div class="confidence-panel">
                                <div class="confidence-meta">
                                    <span>${App.escape(category)}</span>
                                    <strong>${(safeConfidence * 100).toFixed(1)}%</strong>
                                </div>
                                <div class="confidence-track" title="${App.escape(category)} ${(safeConfidence * 100).toFixed(1)}%">
                                    <div class="confidence-fill-visual" style="width:${safeConfidence * 100}%; background:${color};"></div>
                                </div>
                                <div class="confidence-note">${App.escape(category)} confidence from this agent</div>
                            </div>
                            ${agent.error ? `<div class="error-state" style="padding:0;text-align:left">${App.escape(agent.error)}</div>` : ""}
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    },

    renderPaxos(logs) {
        if (!logs.length) return App.empty("No Paxos logs for this request");
        return `<div class="timeline">${logs.map((log) => `
            <div class="timeline-item">
                <strong>${App.escape(log.phase || log.type || "step")}</strong>
                <div>${App.escape(log.message || log.value || JSON.stringify(log))}</div>
            </div>
        `).join("")}</div>`;
    },

    categoryColor(category, index) {
        const colors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2"];
        if (category.includes("垃圾") || category.toLowerCase().includes("spam")) return "#dc2626";
        if (category.includes("工作") || category.toLowerCase().includes("work")) return "#16a34a";
        if (category.includes("会议") || category.toLowerCase().includes("meeting")) return "#2563eb";
        if (category.includes("可疑") || category.toLowerCase().includes("suspicious")) return "#d97706";
        return colors[index % colors.length];
    }
};
