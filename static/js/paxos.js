const PaxosPage = {
    page: 1,
    limit: 20,
    emailId: "",

    load() {
        const page = document.getElementById("page-paxos");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Paxos Logs</h2>
                    <p class="page-subtitle">Consensus logs, per-email filtering, and conflict demonstration.</p>
                </div>
                <button class="btn" type="button" onclick="PaxosPage.fetchLogs()">Refresh</button>
            </div>
            <div class="card">
                <div class="toolbar">
                    <input id="paxos-email-id" class="form-control" style="max-width:180px" placeholder="Email ID" value="${App.escape(this.emailId)}">
                    <button class="btn" type="button" onclick="PaxosPage.applyEmailFilter()">Filter by email</button>
                    <button class="btn" type="button" onclick="PaxosPage.clearEmailFilter()">Clear</button>
                    <button class="btn btn-primary" type="button" onclick="PaxosPage.runDemo()">Run conflict demo</button>
                </div>
                <div id="paxos-demo"></div>
                <div id="paxos-log-list"></div>
            </div>
        `;
        this.fetchLogs();
    },

    applyEmailFilter() {
        this.emailId = document.getElementById("paxos-email-id").value.trim();
        this.page = 1;
        this.fetchLogs();
    },

    clearEmailFilter() {
        this.emailId = "";
        this.page = 1;
        this.load();
    },

    async fetchLogs() {
        const box = document.getElementById("paxos-log-list");
        App.setLoading(box);
        try {
            const params = new URLSearchParams({ page: this.page, limit: this.limit });
            if (this.emailId) params.set("email_id", this.emailId);
            const result = await API.get(`/api/paxos/logs?${params.toString()}`);
            this.renderLogs(result);
        } catch (error) {
            App.setError(box, error, () => this.fetchLogs());
            App.showToast(error.message, "error");
        }
    },

    renderLogs(result) {
        const box = document.getElementById("paxos-log-list");
        const rows = result.data || [];
        if (!rows.length) {
            box.innerHTML = App.empty("No Paxos logs");
            return;
        }
        box.innerHTML = `
            <div class="table-wrap">
                <table>
                    <thead><tr><th>Created</th><th>Email ID</th><th>Proposal ID</th><th>Phase</th><th>Proposer</th><th>Value</th><th>Result</th></tr></thead>
                    <tbody>${rows.map((log) => `
                        <tr>
                            <td>${App.formatDate(log.created_at)}</td>
                            <td><button class="link-button" type="button" onclick="PaxosPage.viewEmailLogs(${log.email_id})">${App.escape(log.email_id ?? "-")}</button></td>
                            <td>${App.escape(log.proposal_id ?? "-")}</td>
                            <td>${App.escape(log.phase || "-")}</td>
                            <td>${App.escape(log.proposer || "-")}</td>
                            <td>${App.escape(log.value || "-")}</td>
                            <td><span class="badge ${log.result === "success" ? "badge-success" : "badge-muted"}">${App.escape(log.result || "-")}</span></td>
                        </tr>
                    `).join("")}</tbody>
                </table>
            </div>
            ${App.renderPagination(result.total || 0, result.page || this.page, result.limit || this.limit, "goPaxosPage")}
        `;
    },

    async viewEmailLogs(emailId) {
        try {
            const result = await API.get(`/api/paxos/logs/${emailId}`);
            const logs = result.logs || [];
            App.showModal(`
                <div class="modal-header">
                    <h3>Paxos logs for email #${emailId}</h3>
                    <button class="modal-close" type="button" onclick="App.closeModal()">x</button>
                </div>
                ${logs.length ? `<div class="timeline">${logs.map((log) => `
                    <div class="timeline-item">
                        <strong>${App.escape(log.phase || "-")}</strong>
                        <div>${App.escape(log.value || "-")} | ${App.escape(log.result || "-")}</div>
                        <div class="text-muted">${App.formatDate(log.created_at)}</div>
                    </div>
                `).join("")}</div>` : App.empty("No logs for this email")}
            `);
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async runDemo() {
        const box = document.getElementById("paxos-demo");
        App.setLoading(box, "Running Paxos conflict demo...");
        try {
            const result = await API.post("/api/paxos/demo-conflict", {});
            box.innerHTML = `
                <div class="demo-panel">
                    <strong>Conflict demo result</strong>
                    <div class="timeline">${(result.log || []).map((item) => `
                        <div class="timeline-item">${App.escape(item.message || JSON.stringify(item))}</div>
                    `).join("")}</div>
                </div>
            `;
        } catch (error) {
            App.setError(box, error);
            App.showToast(error.message, "error");
        }
    }
};

function goPaxosPage(page) {
    PaxosPage.page = page;
    PaxosPage.fetchLogs();
}
