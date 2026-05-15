const EmailPage = {
    page: 1,
    limit: 10,
    search: "",
    category: "",
    selected: new Set(),

    load() {
        const page = document.getElementById("page-email");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Email Management</h2>
                    <p class="page-subtitle">Create, edit, batch classify, delete, and inspect stored emails.</p>
                </div>
                <button class="btn btn-primary" type="button" onclick="EmailPage.openCreateModal()">New Email</button>
            </div>
            <div class="card">
                <div class="toolbar">
                    <input id="email-search" class="form-control" style="max-width:320px" placeholder="Search sender, subject, content" value="${App.escape(this.search)}">
                    <select id="email-category" class="form-control" style="max-width:180px">
                        <option value="">All categories</option>
                        <option value="会议通知">Meeting</option>
                        <option value="垃圾邮件">Spam</option>
                        <option value="工作汇报">Work report</option>
                        <option value="可疑邮件">Suspicious</option>
                    </select>
                    <button class="btn" type="button" onclick="EmailPage.applyFilters()">Filter</button>
                    <button class="btn" type="button" onclick="EmailPage.resetFilters()">Reset</button>
                </div>
                <div id="email-batch-bar" class="batch-actions hidden">
                    <strong><span id="email-selected-count">0</span> selected</strong>
                    <button class="btn btn-sm btn-primary" type="button" onclick="EmailPage.batchClassify()">Batch classify</button>
                    <button class="btn btn-sm btn-danger" type="button" onclick="EmailPage.batchDelete()">Batch delete</button>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.clearSelection()">Clear</button>
                </div>
                <div style="display:flex;gap:8px;margin-bottom:8px">
                    <button class="btn btn-sm btn-success" type="button" onclick="EmailPage.exportCSV()">Export CSV</button>
                    <label class="btn btn-sm" style="cursor:pointer;margin:0">
                        Import CSV
                        <input type="file" accept=".csv" style="display:none" onchange="EmailPage.importCSV(this.files[0])">
                    </label>
                </div>
                <div id="email-list"></div>
            </div>
        `;
        document.getElementById("email-category").value = this.category;
        document.getElementById("email-search").addEventListener("keydown", (event) => {
            if (event.key === "Enter") this.applyFilters();
        });
        this.fetchList();
    },

    async fetchList() {
        const box = document.getElementById("email-list");
        App.setLoading(box);
        const params = new URLSearchParams({
            page: this.page,
            limit: this.limit,
            search: this.search,
            category: this.category
        });
        try {
            const result = await API.get(`/api/emails?${params.toString()}`);
            this.renderList(result);
        } catch (error) {
            App.setError(box, error, () => this.fetchList());
            App.showToast(error.message, "error");
        }
    },

    renderList(result) {
        const box = document.getElementById("email-list");
        const rows = result.data || [];
        if (!rows.length) {
            box.innerHTML = App.empty("No emails found");
            this.updateBatchBar();
            return;
        }
        const allChecked = rows.length > 0 && rows.every((mail) => this.selected.has(mail.id));
        const htmlRows = rows.map((mail) => `
            <tr class="${this.selected.has(mail.id) ? "selected-row" : ""}">
                <td><input type="checkbox" ${this.selected.has(mail.id) ? "checked" : ""} onchange="EmailPage.toggleSelect(${mail.id}, this.checked)"></td>
                <td>${mail.id}</td>
                <td>${App.escape(mail.sender)}</td>
                <td><div class="text-truncate">${App.escape(mail.subject || "-")}</div></td>
                <td>${App.badge(mail.final_category)}</td>
                <td>${App.escape(mail.final_method || "-")}</td>
                <td>${App.formatDate(mail.created_at)}</td>
                <td>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.view(${mail.id})">Detail</button>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.openEditModal(${mail.id})">Edit</button>
                    <button class="btn btn-sm btn-primary" type="button" onclick="EmailPage.classify(${mail.id})">Classify</button>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.viewClassifyResult(${mail.id})">Result</button>
                    <button class="btn btn-sm btn-danger" type="button" onclick="EmailPage.remove(${mail.id})">Delete</button>
                </td>
            </tr>
        `).join("");
        box.innerHTML = `
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th><input type="checkbox" ${allChecked ? "checked" : ""} onchange="EmailPage.togglePageSelection(this.checked)"></th>
                            <th>ID</th><th>Sender</th><th>Subject</th><th>Category</th><th>Method</th><th>Created</th><th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>${htmlRows}</tbody>
                </table>
            </div>
            ${App.renderPagination(result.total || 0, result.page || this.page, result.limit || this.limit, "goEmailPage")}
        `;
        this.currentRows = rows;
        this.updateBatchBar();
    },

    toggleSelect(id, checked) {
        if (checked) this.selected.add(id);
        else this.selected.delete(id);
        this.fetchList();
    },

    togglePageSelection(checked) {
        (this.currentRows || []).forEach((mail) => {
            if (checked) this.selected.add(mail.id);
            else this.selected.delete(mail.id);
        });
        this.fetchList();
    },

    clearSelection() {
        this.selected.clear();
        this.fetchList();
    },

    updateBatchBar() {
        const bar = document.getElementById("email-batch-bar");
        const count = document.getElementById("email-selected-count");
        if (!bar || !count) return;
        count.textContent = this.selected.size;
        bar.classList.toggle("hidden", this.selected.size === 0);
    },

    applyFilters() {
        this.search = document.getElementById("email-search").value.trim();
        this.category = document.getElementById("email-category").value;
        this.page = 1;
        this.fetchList();
    },

    resetFilters() {
        this.search = "";
        this.category = "";
        this.page = 1;
        this.load();
    },

    openCreateModal() {
        this.showEmailForm("New Email", {}, "EmailPage.create()");
    },

    async openEditModal(id) {
        try {
            const result = await API.get(`/api/emails/${id}`);
            this.showEmailForm(`Edit Email #${id}`, result.email || {}, `EmailPage.update(${id})`);
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    showEmailForm(title, mail, action) {
        App.showModal(`
            <div class="modal-header">
                <h3>${App.escape(title)}</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">x</button>
            </div>
            <div class="form-grid">
                <div class="form-group"><label>Sender</label><input id="email-form-sender" value="${App.escape(mail.sender || "")}" placeholder="sender@example.com"></div>
                <div class="form-group"><label>Subject</label><input id="email-form-subject" value="${App.escape(mail.subject || "")}" placeholder="Email subject"></div>
                <div class="form-group"><label>Content</label><textarea id="email-form-content" placeholder="Email content">${App.escape(mail.content || "")}</textarea></div>
            </div>
            <div class="form-actions">
                <button class="btn" type="button" onclick="App.closeModal()">Cancel</button>
                <button class="btn btn-primary" type="button" onclick="${action}">Save</button>
            </div>
        `);
    },

    formData() {
        return {
            sender: document.getElementById("email-form-sender").value.trim(),
            subject: document.getElementById("email-form-subject").value.trim(),
            content: document.getElementById("email-form-content").value.trim()
        };
    },

    async create() {
        const data = this.formData();
        if (!data.sender) {
            App.showToast("Sender is required", "warning");
            return;
        }
        try {
            await API.post("/api/emails", data);
            App.closeModal();
            App.showToast("Email created");
            this.fetchList();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async update(id) {
        const data = this.formData();
        if (!data.sender) {
            App.showToast("Sender is required", "warning");
            return;
        }
        try {
            await API.put(`/api/emails/${id}`, data);
            App.closeModal();
            App.showToast("Email updated");
            this.fetchList();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async view(id) {
        try {
            const result = await API.get(`/api/emails/${id}`);
            this.showEmailDetail(result, `Email #${id}`);
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async viewClassifyResult(id) {
        try {
            const result = await API.get(`/api/classify/${id}/result`);
            this.showEmailDetail(result, `Classification Result #${id}`);
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    showEmailDetail(result, title) {
        const mail = result.email || {};
        const classifications = result.classifications || [];
        const logs = result.paxos_logs || [];
        const finalResult = result.final_result;
        App.showModal(`
            <div class="modal-header">
                <h3>${App.escape(title)}</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">x</button>
            </div>
            <div class="grid">
                <div><strong>Sender:</strong> ${App.escape(mail.sender || "-")}</div>
                <div><strong>Subject:</strong> ${App.escape(mail.subject || "-")}</div>
                <div><strong>Content:</strong><p>${App.escape(mail.content || "-")}</p></div>
                <div><strong>Final:</strong> ${finalResult ? App.badge(finalResult.category) + " " + App.escape(finalResult.method || "") : '<span class="text-muted">Unclassified</span>'}</div>
            </div>
            <h4>Agent Results</h4>
            ${this.renderClassifications(classifications)}
            <h4>Paxos Logs</h4>
            ${this.renderLogs(logs)}
        `);
    },

    renderClassifications(items) {
        if (!items.length) return App.empty("No agent results");
        return `
            <div class="table-wrap"><table>
                <thead><tr><th>Agent</th><th>Method</th><th>Category</th><th>Confidence</th></tr></thead>
                <tbody>${items.map((item) => `
                    <tr>
                        <td>${App.escape(item.agent_name || "-")}</td>
                        <td>${App.escape(item.method || "-")}</td>
                        <td>${App.badge(item.category)}</td>
                        <td>${App.percent(item.confidence)}</td>
                    </tr>
                `).join("")}</tbody>
            </table></div>
        `;
    },

    renderLogs(items) {
        if (!items.length) return App.empty("No Paxos logs");
        return `<div class="timeline">${items.map((log) => `
            <div class="timeline-item">
                <strong>${App.escape(log.phase || "-")}</strong>
                <div class="text-muted">proposal ${App.escape(log.proposal_id || "-")} | ${App.escape(log.value || "-")} | ${App.escape(log.result || "-")}</div>
            </div>
        `).join("")}</div>`;
    },

    async classify(id) {
        await this.runBatch("classify", [id], "Classifying email...", "Classification complete");
    },

    async batchClassify() {
        await this.runBatch("classify", Array.from(this.selected), "Classifying selected emails...", "Batch classification complete");
    },

    async batchDelete() {
        if (!confirm(`Delete ${this.selected.size} selected email(s)?`)) return;
        await this.runBatch("delete", Array.from(this.selected), "Deleting selected emails...", "Batch delete complete");
    },

    async runBatch(action, ids, loadingMessage, successMessage) {
        if (!ids.length) return;
        try {
            App.showToast(loadingMessage, "info");
            const result = await API.post("/api/emails/batch", { action, email_ids: ids });
            const failures = (result.results || []).filter((item) => !item.success);
            if (failures.length) throw new Error(`${failures.length} item(s) failed`);
            ids.forEach((id) => this.selected.delete(id));
            App.showToast(successMessage);
            this.fetchList();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    async remove(id) {
        if (!confirm("Delete this email?")) return;
        try {
            await API.delete(`/api/emails/${id}`);
            this.selected.delete(id);
            App.showToast("Email deleted");
            this.fetchList();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    },

    exportCSV() {
        window.open("/api/emails/export", "_blank");
    },

    async importCSV(file) {
        if (!file) return;
        if (!file.name.endsWith(".csv")) {
            App.showToast("Please select a CSV file", "warning");
            return;
        }
        const formData = new FormData();
        formData.append("file", file);
        try {
            const response = await fetch("/api/emails/import", { method: "POST", body: formData });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Import failed");
            App.showToast(`Imported ${result.imported} email(s)`);
            if (result.errors && result.errors.length) {
                console.warn("Import errors:", result.errors);
            }
            this.fetchList();
        } catch (error) {
            App.showToast(error.message, "error");
        }
    }
};

function goEmailPage(page) {
    EmailPage.page = page;
    EmailPage.fetchList();
}
