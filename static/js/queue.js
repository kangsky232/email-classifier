let mqTimer = null;
let mqSocket = null;
let mqFlowLog = [];

const QueuePage = {
    cleanup() {
        if (mqTimer) { clearInterval(mqTimer); mqTimer = null; }
        if (mqSocket) { mqSocket.disconnect(); mqSocket = null; }
    },

    _archRow(nodes) {
        let html = '<div style="display:flex;align-items:center;margin-bottom:6px;">';
        nodes.forEach((n, i) => {
            html += `<span style="background:${n.bg};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">${n.label}</span>`;
            if (i < nodes.length - 1) {
                html += `<span class="arch-arrow"><span class="flow-particle"></span><span class="flow-particle"></span></span>`;
            }
        });
        html += '</div>';
        return html;
    },

    _animateNumber(el, target, suffix) {
        suffix = suffix || '';
        const duration = 600;
        const start = performance.now();
        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(target * ease) + suffix;
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    },

    async load() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById("page-queue");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("queue.title")}</h2>
                    <p class="page-subtitle">${t("queue.subtitle")}</p>
                </div>
                <div style="display:flex;gap:8px;">
                    <button class="btn btn-primary" type="button" onclick="QueuePage.runDemo(this)">${t("queue.run_demo")}</button>
                    <button class="btn" type="button" onclick="QueuePage.load()">${t("common.refresh")}</button>
                </div>
            </div>
            <div class="stats-grid" id="mq-overview"></div>

            <div class="card" style="margin-top:16px;">
                <div class="card-header"><h3>${t("queue.live_flow")}</h3></div>
                <div id="mq-flow-container" style="min-height:180px;max-height:350px;overflow-y:auto;padding:8px;background:#fafbfc;border-radius:6px;">
                    <div style="text-align:center;padding:40px;color:#999;">
                        <div style="font-size:32px;">📡</div>
                        <div style="margin-top:8px;">${t("queue.waiting")}</div>
                        <div style="font-size:12px;">${(typeof I18N !== 'undefined' && I18N.lang === 'en') ? 'Click "Run Demo" or classify an email to see MQ activity' : '点击"运行演示"或分类一封邮件以查看 MQ 活动'}</div>
                    </div>
                </div>
            </div>

            <div class="grid two" style="margin-top:16px;">
                <div class="card">
                    <div class="card-header"><h3>${t("queue.queues_header")}</h3></div>
                    <div id="queueData"></div>
                </div>
                <div class="card">
                    <div class="card-header"><h3>${t("queue.recent_messages")}</h3></div>
                    <div id="queueMessageList" style="max-height:400px;overflow-y:auto;"></div>
                </div>
            </div>
            <div class="card" style="margin-top:16px;">
                <div class="card-header"><h3>${t("queue.architecture")}</h3></div>
                <div style="font-size:13px;color:#666;line-height:2;padding:8px 0;">
                    ${this._archRow([
                        {bg:'#1890ff',label:'Flask App'},
                        {bg:'#722ed1',label:'email_input'},
                        {bg:'#13c2c2',label:'Consumer'},
                        {bg:'#1890ff',label:'LLM Agent'}
                    ])}
                    ${this._archRow([
                        {bg:'#1890ff',label:'LLM Agent'},
                        {bg:'#722ed1',label:'classification_result'},
                        {bg:'#13c2c2',label:'Consumer'},
                        {bg:'#52c41a',label:'Log'}
                    ])}
                    ${this._archRow([
                        {bg:'#1890ff',label:'Proposer'},
                        {bg:'#722ed1',label:'paxos_vote'},
                        {bg:'#eb2f96',label:'Acceptors'}
                    ])}
                    ${this._archRow([
                        {bg:'#1890ff',label:'LLM Agent'},
                        {bg:'#722ed1',label:'final_action'},
                        {bg:'#52c41a',label:'Database'}
                    ])}
                </div>
            </div>
        `;
        this.initSocket();
        this.startTimer();
    },

    initSocket() {
        if (mqSocket) { mqSocket.disconnect(); mqSocket = null; }
        try {
            mqSocket = io({ transports: ['websocket', 'polling'] });
            mqSocket.on('connect', () => {
                this.addFlowEntry('system', 'WebSocket connected', 'info');
            });
            mqSocket.on('mq_event', (data) => {
                const queue = data.queue || 'unknown';
                const type = data.type || 'message';
                const emailId = data.email_id || '';
                const category = data.category || '';
                const mode = data.mode || '';
                let detail = `queue=<b>${queue}</b> type=<b>${type}</b>`;
                if (emailId) detail += ` email_id=<b>${emailId}</b>`;
                if (category) detail += ` → <b>${category}</b>`;
                if (mode) detail += ` [${mode}]`;
                this.addFlowEntry(queue, detail, 'mq');
            });
            mqSocket.on('classify_progress', (data) => {
                const stage = data.stage || '';
                const msg = data.message || '';
                this.addFlowEntry('classify', `Stage: <b>${stage}</b> ${msg}`, 'classify');
            });
            mqSocket.on('disconnect', () => {
                this.addFlowEntry('system', 'WebSocket disconnected', 'warn');
            });
        } catch (e) {
            console.error('SocketIO init failed:', e);
        }
    },

    addFlowEntry(source, detail, type) {
        const container = document.getElementById('mq-flow-container');
        if (!container) return;

        const now = new Date().toLocaleTimeString();
        const colors = {
            'mq': '#722ed1',
            'classify': '#1890ff',
            'system': '#8c8c8c',
            'demo': '#52c41a',
            'warn': '#faad14',
            'info': '#1890ff'
        };
        const color = colors[type] || '#666';
        const icons = {
            'email_input': '📧',
            'classification_result': '🏷',
            'paxos_proposal': '🗳',
            'final_action': '✅',
            'classify': '⚡',
            'system': '🔧',
            'demo': '🧪'
        };
        const icon = icons[source] || '📨';

        if (container.querySelector('[style*="text-align:center"]')) {
            container.innerHTML = '';
        }

        const entry = document.createElement('div');
        entry.style.cssText = 'display:flex;align-items:flex-start;padding:5px 8px;border-bottom:1px solid #f0f0f0;gap:8px;animation:fadeIn 0.3s;';
        entry.innerHTML = `
            <span style="color:#bbb;font-size:11px;min-width:64px;white-space:nowrap;">${now}</span>
            <span style="font-size:14px;">${icon}</span>
            <div style="flex:1;font-size:12px;color:${color};">${detail}</div>
        `;
        container.insertBefore(entry, container.firstChild);

        if (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }

        mqFlowLog.push({ time: now, source, detail, type });
        if (mqFlowLog.length > 100) mqFlowLog.shift();
    },

    async runDemo(btn) {
        btn = btn || event.target;
        btn.disabled = true;
        btn.textContent = 'Running...';
        this.addFlowEntry('demo', 'Starting MQ demo...', 'demo');

        try {
            this.addFlowEntry('email_input', 'Publishing test email to <b>email_input</b> queue', 'mq');
            const result = await API.post('/api/classify', {
                sender: 'demo@example.com',
                subject: 'MQ Demo Test',
                content: 'This is a test message to demonstrate message queue flow.'
            });

            this.addFlowEntry('classification_result', `Classification result published to <b>classification_result</b> queue`, 'mq');
            if (result.final_category) {
                this.addFlowEntry('final_action', `Final category: <b>${result.final_category}</b> (method: ${result.method})`, 'mq');
            }
            this.addFlowEntry('demo', 'Demo complete!', 'demo');
            App.showToast("Demo complete - check the flow log above");
        } catch (error) {
            this.addFlowEntry('demo', `Demo error: ${error.message}`, 'warn');
            App.showToast("Demo failed: " + error.message, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = 'Run Demo';
        }
    },

    async fetchStatus() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        try {
            const data = await API.get('/api/queue/status');

            const overview = document.getElementById('mq-overview');
            if (overview) {
                const modeColor = data.using_rabbitmq ? '#52c41a' : '#faad14';
                const modeLabel = data.using_rabbitmq ? 'RabbitMQ' : 'Memory Queue';
                const totalMsgs = (data.queues || []).reduce((s, q) => s + q.messages, 0);
                const pendingMsgs = (data.queues || []).reduce((s, q) => s + (q.pending || 0), 0);

                overview.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-label">${t("queue.mq_mode")}</div>
                        <div class="stat-value" style="font-size:20px;background:${modeColor};color:#fff;display:inline-block;padding:4px 12px;border-radius:6px;margin-top:8px;">${modeLabel}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">${t("queue.total_messages")}</div>
                        <div class="stat-value" id="mq-total-msgs">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">${t("queue.pending")}</div>
                        <div class="stat-value" id="mq-pending-msgs" style="color:${pendingMsgs > 0 ? '#ff4d4f' : '#52c41a'};">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">${t("queue.queues")}</div>
                        <div class="stat-value" id="mq-queue-count">0</div>
                    </div>
                `;

                const totalEl = document.getElementById('mq-total-msgs');
                const pendingEl = document.getElementById('mq-pending-msgs');
                const queueEl = document.getElementById('mq-queue-count');
                if (totalEl) this._animateNumber(totalEl, totalMsgs);
                if (pendingEl) this._animateNumber(pendingEl, pendingMsgs);
                if (queueEl) this._animateNumber(queueEl, (data.queues || []).length);
            }

            const container = document.getElementById('queueData');
            if (container) {
                container.innerHTML = '';
                if (data.queues && data.queues.length > 0) {
                    const colors = ['#1890ff', '#722ed1', '#eb2f96', '#52c41a'];
                    data.queues.forEach(function (q, idx) {
                        const color = colors[idx % colors.length];
                        const barHeight = Math.max(4, Math.min(60, q.messages * 8));
                        container.innerHTML += `
                            <div style="display:flex;align-items:center;padding:10px 12px;border-bottom:1px solid #f0f0f0;">
                                <div style="background:${color};min-width:4px;height:${barHeight}px;border-radius:2px;margin-right:12px;transition:height 0.4s;"></div>
                                <div style="flex:1;">
                                    <div style="font-weight:600;font-size:13px;">${q.name}</div>
                                    <div style="font-size:11px;color:#999;">
                                        ${q.messages} msgs &middot; ${q.consumers} consumer &middot; ${q.pending || 0} pending
                                    </div>
                                </div>
                                <div style="font-size:24px;font-weight:700;color:${color};">${q.messages}</div>
                            </div>
                        `;
                    });
                }
            }

            this.fetchMessages();
        } catch (e) {
            console.error('Failed to fetch queue status:', e);
        }
    },

    async fetchMessages() {
        try {
            const data = await API.get('/api/queue/messages?limit=15');
            const container = document.getElementById('queueMessageList');
            if (!container) return;
            container.innerHTML = '';
            if (data.messages && data.messages.length > 0) {
                const icons = {
                    'email_input': '📧', 'classification_result': '🏷',
                    'paxos_proposal': '🗳', 'final_action': '✅'
                };
                data.messages.forEach(function (m, idx) {
                    const time = new Date(m.timestamp * 1000).toLocaleTimeString();
                    const bodyStr = JSON.stringify(m.body).replace(/"/g, '').replace(/[{}]/g, '');
                    container.innerHTML += `
                        <div style="display:flex;align-items:flex-start;padding:6px 0;border-bottom:1px solid #f5f5f5;gap:8px;">
                            <span style="color:#bbb;font-size:11px;min-width:56px;">${time}</span>
                            <span style="font-size:14px;">${icons[m.queue] || '📨'}</span>
                            <div style="flex:1;min-width:0;">
                                <div style="font-size:12px;color:#1890ff;font-weight:600;">${m.queue}</div>
                                <div style="font-size:11px;color:#666;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${bodyStr.substring(0, 80)}</div>
                            </div>
                        </div>
                    `;
                });
            } else {
                const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
                container.innerHTML = `
                    <div style="text-align:center;padding:40px 20px;color:#999;">
                        <div style="font-size:36px;">📬</div>
                        <div style="margin-top:8px;">${t("queue.no_messages")}</div>
                    </div>
                `;
            }
        } catch (e) {
            console.error('Failed to fetch queue messages:', e);
        }
    },

    startTimer() {
        this.stopTimer();
        this.fetchStatus();
        mqTimer = setInterval(() => this.fetchStatus(), 3000);
    },

    stopTimer() {
        if (mqTimer) { clearInterval(mqTimer); mqTimer = null; }
    }
};
