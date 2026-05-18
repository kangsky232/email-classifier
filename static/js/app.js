const API = {
    async request(url, options = {}) {
        const config = {
            method: options.method || "GET",
            headers: { "Content-Type": "application/json", ...(options.headers || {}) }
        };
        if (options.body !== undefined) {
            config.body = JSON.stringify(options.body);
        }
        const response = await fetch(url, config);
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = {};
        }
        if (response.status === 401 && !url.includes('/api/auth/')) {
            if (typeof AuthPage !== 'undefined') {
                AuthPage.user = null;
                AuthPage.showLoginWall();
            }
            throw new Error("请先登录");
        }
        if (!response.ok) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }
        return data;
    },
    get(url) { return this.request(url); },
    post(url, body) { return this.request(url, { method: "POST", body }); },
    put(url, body) { return this.request(url, { method: "PUT", body }); },
    delete(url, body) { return this.request(url, { method: "DELETE", body }); }
};

// Global error handler for unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    App.showToast('An unexpected error occurred', 'error');
    event.preventDefault();
});

const App = {
    currentPage: "email",
    pages: {
        email: () => EmailPage.load(),
        classify: () => ClassifyPage.load(),
        monitor: () => MonitorPage.load(),
        paxos: () => PaxosPage.load(),
        stats: () => StatsPage.load(),
        queue: () => QueuePage.load(),
        settings: () => SettingsPage.load(),
        cluster: () => ClusterPage.render()
    },

    _currentPageObj: null,

    init() {
        document.querySelectorAll(".nav-item").forEach((item) => {
            item.addEventListener("click", () => this.switchPage(item.dataset.page));
        });
        const modal = document.getElementById("modal-overlay");
        modal.addEventListener("click", (event) => {
            if (event.target === modal) this.closeModal();
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") this.closeModal();
        });
        // Restore dark mode
        if (localStorage.getItem("darkMode") === "true") {
            document.body.classList.add("dark");
            const lbl = document.getElementById("dark-label");
            if (lbl) lbl.textContent = "亮色模式";
        }
        this.loadPage(this.currentPage);
    },

    toggleDark() {
        document.body.classList.toggle("dark");
        const isDark = document.body.classList.contains("dark");
        localStorage.setItem("darkMode", isDark);
        const lbl = document.getElementById("dark-label");
        if (lbl) lbl.textContent = isDark ? "亮色模式" : "暗色模式";
    },

    switchPage(page) {
        if (!this.pages[page]) return;
        this.currentPage = page;
        document.querySelectorAll(".nav-item").forEach((item) => {
            item.classList.toggle("active", item.dataset.page === page);
        });
        document.querySelectorAll(".page").forEach((item) => item.classList.remove("active"));
        document.getElementById(`page-${page}`).classList.add("active");
        this.loadPage(page);
    },

    loadPage(page) {
        // Cleanup previous page resources
        const pageMap = { email: EmailPage, classify: ClassifyPage, monitor: MonitorPage, paxos: PaxosPage, stats: StatsPage, queue: QueuePage, settings: SettingsPage, cluster: ClusterPage };
        const prev = this._currentPageObj;
        if (prev && typeof prev.cleanup === 'function') {
            prev.cleanup();
        }
        this._currentPageObj = pageMap[page] || null;
        this.pages[page]();
    },

    setLoading(container, text = "Loading...") {
        container.innerHTML = `<div class="loading"><div class="spinner"></div>${this.escape(text)}</div>`;
    },

    setError(container, error, retryHandler) {
        const message = error instanceof Error ? error.message : String(error || "Request failed");
        container.innerHTML = `
            <div class="error-state">
                <p>${this.escape(message)}</p>
                ${retryHandler ? '<button class="btn btn-primary" data-retry="1" type="button">Retry</button>' : ""}
            </div>
        `;
        if (retryHandler) {
            container.querySelector("[data-retry]").addEventListener("click", retryHandler);
        }
    },

    empty(text = "No data") {
        return `<div class="empty-state">${this.escape(text)}</div>`;
    },

    showToast(message, type = "success") {
        const container = document.getElementById("toast-container");
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    },

    showModal(html) {
        document.getElementById("modal-content").innerHTML = html;
        document.getElementById("modal-overlay").classList.remove("hidden");
    },

    closeModal() {
        document.getElementById("modal-overlay").classList.add("hidden");
        document.getElementById("modal-content").innerHTML = "";
    },

    renderPagination(total, page, limit, onPageChangeName) {
        const totalPages = Math.max(Math.ceil((Number(total) || 0) / limit), 1);
        if (totalPages <= 1) return "";
        const start = Math.max(1, page - 2);
        const end = Math.min(totalPages, start + 4);
        const buttons = [`<button type="button" ${page <= 1 ? "disabled" : ""} onclick="${onPageChangeName}(${page - 1})">Prev</button>`];
        for (let i = start; i <= end; i += 1) {
            buttons.push(`<button type="button" class="${i === page ? "active" : ""}" onclick="${onPageChangeName}(${i})">${i}</button>`);
        }
        buttons.push(`<button type="button" ${page >= totalPages ? "disabled" : ""} onclick="${onPageChangeName}(${page + 1})">Next</button>`);
        return `<div class="pagination">${buttons.join("")}</div>`;
    },

    formatDate(value) {
        if (!value) return "-";
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    },

    percent(value) {
        const number = Number(value);
        return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "-";
    },

    badge(category) {
        if (!category) return '<span class="badge badge-muted">Unclassified</span>';
        const text = this.escape(category);
        if (category.includes("spam") || category.includes("junk") || category.includes("suspicious") || category.includes("垃圾") || category.includes("可疑")) {
            return `<span class="badge badge-danger">${text}</span>`;
        }
        if (category.includes("work") || category.includes("工作")) return `<span class="badge badge-success">${text}</span>`;
        if (category.includes("meeting") || category.includes("会议")) return `<span class="badge badge-info">${text}</span>`;
        return `<span class="badge">${text}</span>`;
    },

    escape(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    },

    async safeExecute(fn, errorHandler) {
        try {
            return await fn();
        } catch (error) {
            console.error('Operation failed:', error);
            if (errorHandler) errorHandler(error);
            else App.showToast(error.message || 'Operation failed', 'error');
        }
    }
};

// WebSocket 连接
let socket = null;

function initSocket() {
    try {
        socket = io();
        socket.on('connect', () => console.log('WebSocket connected'));
        socket.on('disconnect', () => console.log('WebSocket disconnected'));
    } catch (e) {
        console.warn('WebSocket init failed:', e);
    }
}

window.addEventListener("DOMContentLoaded", async () => {
    App.init();
    await AuthPage.init();
    initSocket();
    // Apply i18n translations to nav items
    if (typeof I18N !== 'undefined') {
        I18N.setLang(I18N.lang);
    }
});
