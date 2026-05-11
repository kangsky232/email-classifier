const API_BASE = '';
let currentPage = 'email';
let socket = null;

const API = {
    async get(url) {
        const resp = await fetch(API_BASE + url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    },
    async post(url, data) {
        const resp = await fetch(API_BASE + url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    },
    async put(url, data) {
        const resp = await fetch(API_BASE + url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    },
    async delete(url, data) {
        const resp = await fetch(API_BASE + url, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }
};

const App = {
    init() {
        this.initSocket();
        this.initNav();
        this.initModal();
        loadPage('email');
    },

    initSocket() {
        socket = io();
        
        socket.on('connect', () => {
            const statusEl = document.getElementById('ws-status');
            statusEl.innerHTML = '<span class="status-dot online"></span><span>已连接</span>';
            console.log('WebSocket已连接');
        });

        socket.on('disconnect', () => {
            const statusEl = document.getElementById('ws-status');
            statusEl.innerHTML = '<span class="status-dot offline"></span><span>已断开</span>';
            console.log('WebSocket已断开');
        });

        socket.on('classify_progress', (data) => {
            if (currentPage === 'classify') {
                ClassifyPage.handleProgress(data);
            }
        });
    },

    initNav() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const page = item.dataset.page;
                this.switchPage(page);
            });
        });
    },

    initModal() {
        document.getElementById('modal-overlay').addEventListener('click', e => {
            if (e.target === e.currentTarget) this.closeModal();
        });
    },

    switchPage(page) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.querySelector(`[data-page="${page}"]`).classList.add('active');
        document.getElementById(`page-${page}`).classList.add('active');
        currentPage = page;
        loadPage(page);
    },

    showToast(msg, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    },

    showModal(html) {
        document.getElementById('modal-content').innerHTML = html;
        document.getElementById('modal-overlay').classList.remove('hidden');
    },

    closeModal() {
        document.getElementById('modal-overlay').classList.add('hidden');
    },

    renderPagination(total, page, limit, onPageChange) {
        const totalPages = Math.ceil(total / limit);
        if (totalPages <= 1) return '';
        let html = '<div class="pagination">';
        html += `<button ${page <= 1 ? 'disabled' : ''} onclick="${onPageChange}(${page-1})">上一页</button>`;
        for (let i = 1; i <= totalPages && i <= 7; i++) {
            html += `<button class="${i === page ? 'active' : ''}" onclick="${onPageChange}(${i})">${i}</button>`;
        }
        html += `<button ${page >= totalPages ? 'disabled' : ''} onclick="${onPageChange}(${page+1})">下一页</button>`;
        html += '</div>';
        return html;
    }
};

function loadPage(page) {
    switch(page) {
        case 'email': loadEmailPage(); break;
        case 'classify': loadClassifyPage(); break;
        case 'monitor': loadMonitorPage(); break;
        case 'remote': RemotePage.render(); break;
        case 'compare': ComparePage.render(); break;
        case 'paxos': loadPaxosPage(); break;
        case 'stats': loadStatsPage(); break;
        case 'settings': loadSettingsPage(); break;
    }
}

function api(url, options = {}) {
    return API.get(url).catch(e => {
        console.error('API Error:', e);
        App.showToast('请求失败', 'error');
        return null;
    });
}

function showToast(msg, type = 'success') {
    App.showToast(msg, type);
}

function showModal(html) {
    App.showModal(html);
}

function hideModal() {
    App.closeModal();
}

document.addEventListener('DOMContentLoaded', () => App.init());
