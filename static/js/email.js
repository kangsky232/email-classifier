const EmailPage = {
    page: 1,
    limit: 10,
    search: "",
    category: "",
    selected: new Set(),

    load() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById("page-email");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("email.title")}</h2>
                    <p class="page-subtitle">${t("email.subtitle")}</p>
                </div>
                <div style="display:flex;gap:8px;">
                    <button class="btn btn-primary" type="button" onclick="EmailPage.openCreateModal()">${t("email.new")}</button>
                </div>
            </div>
            <div class="card">
                <div class="toolbar">
                    <input id="email-search" class="form-control" style="max-width:320px" placeholder="${t("email.search")}" value="${App.escape(this.search)}">
                    <select id="email-category" class="form-control" style="max-width:180px">
                        <option value="">${t("email.all_categories")}</option>
                        <option value="会议通知">${t("email.meeting")}</option>
                        <option value="垃圾邮件">${t("email.spam")}</option>
                        <option value="工作汇报">${t("email.work")}</option>
                        <option value="可疑邮件">${t("email.suspicious")}</option>
                    </select>
                    <button class="btn" type="button" onclick="EmailPage.applyFilters()">${t("common.filter")}</button>
                    <button class="btn" type="button" onclick="EmailPage.resetFilters()">${t("common.reset")}</button>
                </div>
                <div id="email-batch-bar" class="batch-actions hidden">
                    <strong><span id="email-selected-count">0</span> ${t("email.selected")}</strong>
                    <button class="btn btn-sm btn-primary" type="button" onclick="EmailPage.batchClassify()">${t("email.batch_classify")}</button>
                    <button class="btn btn-sm btn-danger" type="button" onclick="EmailPage.batchDelete()">${t("email.batch_delete")}</button>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.clearSelection()">${t("classify.clear")}</button>
                </div>
                <div style="display:flex;gap:8px;margin-bottom:8px">
                    <button class="btn btn-sm btn-success" type="button" onclick="EmailPage.exportCSV()">${t("email.export_csv")}</button>
                    <label class="btn btn-sm" style="cursor:pointer;margin:0">
                        ${t("email.import_csv")}
                        <input type="file" accept=".csv" style="display:none" onchange="EmailPage.importCSV(this.files[0])">
                    </label>
                    <button class="btn btn-sm btn-danger" type="button" onclick="EmailPage.clearAll()">${t("email.clear_all")}</button>
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
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById("email-list");
        const rows = result.data || [];
        if (!rows.length) {
            box.innerHTML = App.empty(t("email.no_emails"));
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
                    <button class="btn btn-sm" type="button" onclick="EmailPage.view(${mail.id})">${t("email.detail")}</button>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.openEditModal(${mail.id})">${t("email.edit")}</button>
                    <button class="btn btn-sm btn-primary" type="button" onclick="EmailPage.classify(${mail.id})">${t("email.classify")}</button>
                    <button class="btn btn-sm" type="button" onclick="EmailPage.viewClassifyResult(${mail.id})">${t("email.result")}</button>
                    <button class="btn btn-sm btn-danger" type="button" onclick="EmailPage.remove(${mail.id})">${t("email.delete")}</button>
                </td>
            </tr>
        `).join("");
        box.innerHTML = `
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th><input type="checkbox" ${allChecked ? "checked" : ""} onchange="EmailPage.togglePageSelection(this.checked)"></th>
                            <th>ID</th><th>${t("email.sender")}</th><th>${t("email.subject")}</th><th>${t("email.category")}</th><th>${t("classify.method")}</th><th>${t("email.created_at")}</th><th>${t("email.actions")}</th>
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
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        this.showEmailForm(t("email.new"), {}, "EmailPage.create()");
    },

    async openEditModal(id) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        try {
            const result = await API.get(`/api/emails/${id}`);
            this.showEmailForm(`${t("email.edit")} #${id}`, result.email || {}, `EmailPage.update(${id})`);
        } catch (error) {
            console.error('Failed to load email for editing:', error);
            App.showToast(error.message, "error");
        }
    },

    showEmailForm(title, mail, action) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        App.showModal(`
            <div class="modal-header">
                <h3>${App.escape(title)}</h3>
                <button class="modal-close" type="button" onclick="App.closeModal()">x</button>
            </div>
            <div class="form-grid">
                <div class="form-group"><label>${t("email.sender")}</label><input id="email-form-sender" value="${App.escape(mail.sender || "")}" placeholder="sender@example.com"></div>
                <div class="form-group"><label>${t("email.subject")}</label><input id="email-form-subject" value="${App.escape(mail.subject || "")}" placeholder="Email subject"></div>
                <div class="form-group"><label>${t("email.content")}</label><textarea id="email-form-content" placeholder="${t("email.content")}">${App.escape(mail.content || "")}</textarea></div>
            </div>
            <div class="form-actions">
                <button class="btn" type="button" onclick="App.closeModal()">${t("common.cancel")}</button>
                <button class="btn btn-primary" type="button" onclick="${action}">${t("common.save")}</button>
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
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const data = this.formData();
        if (!data.sender) {
            App.showToast(t("email.sender") + " " + t("common.error"), "warning");
            return;
        }
        try {
            await API.post("/api/emails", data);
            App.closeModal();
            App.showToast(t("common.success"));
            this.fetchList();
        } catch (error) {
            console.error('Failed to create email:', error);
            App.showToast(error.message, "error");
        }
    },

    async update(id) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const data = this.formData();
        if (!data.sender) {
            App.showToast(t("email.sender") + " " + t("common.error"), "warning");
            return;
        }
        try {
            await API.put(`/api/emails/${id}`, data);
            App.closeModal();
            App.showToast(t("common.success"));
            this.fetchList();
        } catch (error) {
            console.error('Failed to update email:', error);
            App.showToast(error.message, "error");
        }
    },

    async view(id) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        try {
            const result = await API.get(`/api/emails/${id}`);
            this.showEmailDetail(result, `${t("email.detail")} #${id}`);
        } catch (error) {
            console.error('Failed to load email details:', error);
            App.showToast(error.message, "error");
        }
    },

    async viewClassifyResult(id) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        try {
            const result = await API.get(`/api/classify/${id}/result`);
            this.showEmailDetail(result, `${t("email.result")} #${id}`);
        } catch (error) {
            console.error('Failed to load classification result:', error);
            App.showToast(error.message, "error");
        }
    },

    showEmailDetail(result, title) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
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
                <div><strong>${t("email.sender")}:</strong> ${App.escape(mail.sender || "-")}</div>
                <div><strong>${t("email.subject")}:</strong> ${App.escape(mail.subject || "-")}</div>
                <div><strong>${t("email.content")}:</strong><p>${App.escape(mail.content || "-")}</p></div>
                <div><strong>${t("classify.final_result")}:</strong> ${finalResult ? App.badge(finalResult.category) + " " + App.escape(finalResult.method || "") : '<span class="text-muted">' + t("common.no_data") + '</span>'}</div>
            </div>
            <h4>${t("classify.agent_results")}</h4>
            ${this.renderClassifications(classifications)}
            <h4>${t("classify.paxos_vote")}</h4>
            ${this.renderLogs(logs)}
        `);
    },

    renderClassifications(items) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!items.length) return App.empty(t("classify.no_agent_results"));
        return `
            <div class="table-wrap"><table>
                <thead><tr><th>Agent</th><th>${t("classify.method")}</th><th>${t("email.category")}</th><th>${t("stats.avg_confidence")}</th></tr></thead>
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
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!items.length) return App.empty(t("classify.no_paxos_logs"));
        return `<div class="timeline">${items.map((log) => `
            <div class="timeline-item">
                <strong>${App.escape(log.phase || "-")}</strong>
                <div class="text-muted">proposal ${App.escape(log.proposal_id || "-")} | ${App.escape(log.value || "-")} | ${App.escape(log.result || "-")}</div>
            </div>
        `).join("")}</div>`;
    },

    async classify(id) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        await this.runBatch("classify", [id], `${t("email.classify")} #${id}...`, t("classify.complete"));
    },

    async batchClassify() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        await this.runBatch("classify", Array.from(this.selected), t("classify.classifying"), t("classify.complete"));
    },

    async batchDelete() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const count = this.selected.size;
        if (!count) { App.showToast(t("email.no_emails"), "warning"); return; }
        if (!confirm(t("email.confirm_batch_delete").replace("{count}", count))) return;
        await this.runBatch("delete", Array.from(this.selected), `${t("common.delete")} ${count}...`, `${t("common.success")} (${count})`);
    },

    async runBatch(action, ids, loadingMessage, successMessage) {
        if (!ids.length) return;
        try {
            App.showToast(loadingMessage, "info");
            const result = await API.post("/api/emails/batch", { action, email_ids: ids });
            const failures = (result.results || []).filter((item) => !item.success);
            if (failures.length) {
                console.error('Batch operation partial failures:', failures);
                throw new Error(`${failures.length} item(s) failed`);
            }
            ids.forEach((id) => this.selected.delete(id));
            App.showToast(successMessage);
            this.fetchList();
        } catch (error) {
            console.error('Batch operation failed:', error);
            App.showToast(error.message, "error");
        }
    },

    async remove(id) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!confirm(t("email.confirm_delete"))) return;
        try {
            await API.delete(`/api/emails/${id}`);
            this.selected.delete(id);
            App.showToast(t("common.success"));
            this.fetchList();
        } catch (error) {
            console.error('Failed to delete email:', error);
            App.showToast(error.message, "error");
        }
    },

    async clearAll() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!confirm(t("email.confirm_clear_all"))) return;
        try {
            const result = await API.post("/api/emails/batch", { action: "clear_all", email_ids: [] });
            this.selected.clear();
            if (result.total === 0) {
                App.showToast(t("email.no_clear_target"), "info");
            } else {
                App.showToast(result.message || t("email.clear_success"));
            }
            this.fetchList();
        } catch (error) {
            console.error('Failed to clear all emails:', error);
            App.showToast(error.message, "error");
        }
    },

    exportCSV() {
        window.open("/api/emails/export", "_blank");
    },

    async importCSV(file) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!file) return;
        if (!file.name.endsWith(".csv")) {
            App.showToast(t("email.import_error"), "warning");
            return;
        }
        const formData = new FormData();
        formData.append("file", file);
        try {
            const response = await fetch("/api/emails/import", { method: "POST", body: formData });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || t("email.import_error"));
            App.showToast(t("email.import_success").replace("{count}", result.imported));
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
