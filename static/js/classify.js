const ClassifyPage = {
    mode: "fixed",

    load() {
        const page = document.getElementById("page-classify");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Classify Center</h2>
                    <p class="page-subtitle">Submit email content. AI will automatically classify and extract keywords.</p>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                    <span style="font-size:12px;color:#888;">Mode:</span>
                    <button id="mode-fixed" class="btn btn-sm btn-primary" type="button" onclick="ClassifyPage.setMode('fixed')">Fixed Categories</button>
                    <button id="mode-free" class="btn btn-sm" type="button" onclick="ClassifyPage.setMode('free')">AI Free Classify</button>
                </div>
            </div>
            <div class="grid two">
                <div class="card">
                    <h3 class="card-title">Input</h3>
                    <div id="keyword-section" style="margin-bottom:12px;padding:10px;background:#f0fdf4;border-radius:6px;border:1px dashed #86efac;">
                        <span style="font-size:12px;color:#166534;">💡 After classification, AI will automatically extract keywords from your email content.</span>
                    </div>
                    <div class="form-grid">
                        <div class="form-group"><label>Sender</label><input id="classify-sender" value="boss@company.com"></div>
                        <div class="form-group"><label>Subject</label><input id="classify-subject" value="Project meeting notice"></div>
                        <div class="form-group"><label>Content</label><textarea id="classify-content" style="min-height:120px;">Please attend the project progress meeting tomorrow at 3 PM.</textarea></div>
                    </div>
                    <div class="form-actions">
                        <button class="btn" type="button" onclick="ClassifyPage.clear()">Clear</button>
                        <button id="classify-submit" class="btn btn-primary" type="button" onclick="ClassifyPage.submit()">Submit</button>
                    </div>
                    <div id="free-mode-hint" style="font-size:11px;color:#f59e0b;margin-top:6px;display:none;">Free mode: LLM determines category name automatically. ML agents skip. Requires LLM nodes online.</div>
                </div>
                <div id="classify-result" class="card">
                    <h3 class="card-title">Result</h3>
                    <div class="empty-state">Submit an email to see final category, agent votes, and Paxos logs.</div>
                </div>
            </div>
        `;
    },

    setMode(mode) {
        this.mode = mode;
        document.getElementById("mode-fixed").className = mode === "fixed" ? "btn btn-sm btn-primary" : "btn btn-sm";
        document.getElementById("mode-free").className = mode === "free" ? "btn btn-sm btn-primary" : "btn btn-sm";
        document.getElementById("free-mode-hint").style.display = mode === "free" ? "block" : "none";
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

    async generate() {
        const keywords = document.getElementById("gen-keywords").value.trim();
        const status = document.getElementById("gen-status");
        const btn = document.getElementById("gen-btn");

        if (!keywords) {
            App.showToast("Please enter keywords", "warning");
            return;
        }

        btn.disabled = true;
        status.textContent = "Generating...";
        try {
            const result = await API.post("/api/emails/generate", { keywords });
            if (result.success && result.email) {
                document.getElementById("classify-sender").value = result.email.sender || "";
                document.getElementById("classify-subject").value = result.email.subject || "";
                document.getElementById("classify-content").value = result.email.content || "";
                status.textContent = "Email generated from keywords!";
                App.showToast("Email generated");
            }
        } catch (error) {
            status.textContent = "Generation failed: " + error.message;
            App.showToast(error.message, "error");
        } finally {
            btn.disabled = false;
        }
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
        App.setLoading(box, this.mode === "free" ? "AI free classifying..." : "Classifying...");
        try {
            const endpoint = this.mode === "free" ? "/api/classify/free" : "/api/classify";
            const result = await API.post(endpoint, { sender, subject, content });
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
        const isFree = result.method === "llm_free";

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
                    <div class="stat-label">Final category${isFree ? " (AI free)" : ""}</div>
                    <div class="stat-value" style="${isFree ? 'color:#7c3aed;' : ''}">${App.escape(result.final_category || "-")}</div>
                </div>
                <div class="text-muted">method: ${App.escape(result.method || "-")}${result.consensus ? ` | ${App.escape(result.consensus)}` : ""}${result.email_id ? ` | email id: ${result.email_id}` : ""}</div>
                ${result.message ? `<p>${App.escape(result.message)}</p>` : ""}
            </div>
            <h4>Agent Results</h4>
            ${this.renderAgents(agents)}
            ${paxosLog.length ? `<h4>Paxos Process</h4>${this.renderPaxos(paxosLog)}` : ""}
        `;
    },

    renderAgents(agents) {
        if (!agents.length) return App.empty("No agent results (LLM nodes may be offline or no API Key configured)");
        return `
            <div class="agent-result-grid">
                ${agents.map((agent, index) => {
                    const confidence = Number(agent.confidence) || 0;
                    const safeConfidence = Math.max(0, Math.min(confidence, 1));
                    const category = agent.category || "Unknown";
                    const color = this.categoryColor(category, index);
                    const reason = (agent.details && agent.details.reason) ? agent.details.reason : "";
                    const source = (agent.details && agent.details.source) ? agent.details.source : "";
                    const keywords = agent.keywords || (agent.details && agent.details.keywords) || [];
                    const kwTags = keywords.length ? `
                        <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:4px;">
                            <span style="font-size:10px;color:#7c3aed;">🏷 AI keywords:</span>
                            ${keywords.map(k => `<span style="background:#ede9fe;color:#7c3aed;padding:1px 6px;border-radius:4px;font-size:10px;">${App.escape(k)}</span>`).join("")}
                        </div>` : "";
                    return `
                        <div class="card agent-card agent-result-card" style="box-shadow:none">
                            <div class="agent-head">
                                <strong>${App.escape(agent.agent_name || agent.name || "-")}</strong>
                                ${App.badge(agent.category)}
                                ${source ? `<span style="font-size:10px;color:#888;margin-left:4px;">via ${App.escape(source)}</span>` : ""}
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
                                ${reason ? `<div class="confidence-note" style="font-size:11px;color:#666;margin-top:4px;">${App.escape(reason)}</div>` : ""}
                                ${kwTags}
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
        const colors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#ca8a04"];
        const lower = (category || "").toLowerCase();
        if (lower.includes("垃圾") || lower.includes("spam") || lower.includes("广告")) return "#dc2626";
        if (lower.includes("工作") || lower.includes("work") || lower.includes("报告") || lower.includes("审批")) return "#16a34a";
        if (lower.includes("会议") || lower.includes("meeting") || lower.includes("通知")) return "#2563eb";
        if (lower.includes("可疑") || lower.includes("钓鱼") || lower.includes("安全") || lower.includes("攻击")) return "#d97706";
        if (lower.includes("营销") || lower.includes("推广") || lower.includes("客户")) return "#db2777";
        if (lower.includes("财务") || lower.includes("报销") || lower.includes("付款")) return "#ca8a04";
        return colors[index % colors.length];
    }
};
