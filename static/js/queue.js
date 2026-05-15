let mqTimer = null;

const QueuePage = {
    async load() {
        const page = document.getElementById("page-queue");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Message Queue</h2>
                    <p class="page-subtitle">Real-time message flow between services.</p>
                </div>
                <button class="btn" type="button" onclick="QueuePage.load()">Refresh</button>
            </div>
            <div class="stats-grid" id="mq-overview"></div>
            <div class="grid two" style="margin-top:16px;">
                <div class="card">
                    <div class="card-header"><h3>Queues</h3></div>
                    <div id="queueData"></div>
                </div>
                <div class="card">
                    <div class="card-header"><h3>Recent Messages</h3></div>
                    <div id="queueMessageList" style="max-height:400px;overflow-y:auto;"></div>
                </div>
            </div>
            <div class="card" style="margin-top:16px;">
                <div class="card-header">
                    <h3>Architecture</h3>
                </div>
                <div style="font-size:13px;color:#666;line-height:2;padding:8px 0;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                        <span style="background:#1890ff;color:#fff;padding:2px 8px;border-radius:4px;">Flask App</span>
                        <span>→</span>
                        <span style="background:#722ed1;color:#fff;padding:2px 8px;border-radius:4px;">email_input</span>
                        <span>→</span>
                        <span style="background:#13c2c2;color:#fff;padding:2px 8px;border-radius:4px;">Consumer</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                        <span style="background:#1890ff;color:#fff;padding:2px 8px;border-radius:4px;">Flask App</span>
                        <span>→</span>
                        <span style="background:#722ed1;color:#fff;padding:2px 8px;border-radius:4px;">classification_result</span>
                        <span>→</span>
                        <span style="background:#13c2c2;color:#fff;padding:2px 8px;border-radius:4px;">Consumer</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                        <span style="background:#1890ff;color:#fff;padding:2px 8px;border-radius:4px;">PaxosCoordinator</span>
                        <span>→</span>
                        <span style="background:#722ed1;color:#fff;padding:2px 8px;border-radius:4px;">paxos_proposal</span>
                        <span>→</span>
                        <span style="background:#eb2f96;color:#fff;padding:2px 8px;border-radius:4px;">Acceptor</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="background:#1890ff;color:#fff;padding:2px 8px;border-radius:4px;">Classifier</span>
                        <span>→</span>
                        <span style="background:#722ed1;color:#fff;padding:2px 8px;border-radius:4px;">final_action</span>
                        <span>→</span>
                        <span style="background:#52c41a;color:#fff;padding:2px 8px;border-radius:4px;">Database</span>
                    </div>
                </div>
            </div>
        `;
        this.startTimer();
    },

    async fetchStatus() {
        try {
            const data = await $.get('/api/queue/status');

            const overview = document.getElementById('mq-overview');
            if (overview) {
                const modeColor = data.using_rabbitmq ? '#52c41a' : '#faad14';
                const modeLabel = data.using_rabbitmq ? 'RabbitMQ' : 'Memory Queue';
                const totalMsgs = (data.queues || []).reduce((s, q) => s + q.messages, 0);
                const pendingMsgs = (data.queues || []).reduce((s, q) => s + (q.pending || 0), 0);

                overview.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-label">MQ Mode</div>
                        <div class="stat-value" style="font-size:20px;background:${modeColor};color:#fff;display:inline-block;padding:4px 12px;border-radius:6px;margin-top:8px;">${modeLabel}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total Messages</div>
                        <div class="stat-value">${totalMsgs}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Pending</div>
                        <div class="stat-value" style="color:${pendingMsgs > 0 ? '#ff4d4f' : '#52c41a'};">${pendingMsgs}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Queues</div>
                        <div class="stat-value">${(data.queues || []).length}</div>
                    </div>
                `;
            }

            const container = $(document.getElementById('queueData'));
            container.empty();
            if (data.queues && data.queues.length > 0) {
                const colors = ['#1890ff', '#722ed1', '#eb2f96', '#52c41a'];
                data.queues.forEach(function (q, idx) {
                    const color = colors[idx % colors.length];
                    const barHeight = Math.max(4, Math.min(60, q.messages * 8));
                    container.append(`
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
                    `);
                });
            }

            this.fetchMessages();
        } catch (e) {}
    },

    async fetchMessages() {
        try {
            const data = await $.get('/api/queue/messages?limit=15');
            const container = $(document.getElementById('queueMessageList'));
            container.empty();
            if (data.messages && data.messages.length > 0) {
                const icons = {
                    'email_input': '📧', 'classification_result': '🏷',
                    'paxos_proposal': '🗳', 'final_action': '✅'
                };
                data.messages.forEach(function (m, idx) {
                    const time = new Date(m.timestamp * 1000).toLocaleTimeString();
                    const bodyStr = JSON.stringify(m.body).replace(/"/g, '').replace(/[{}]/g, '');
                    container.append(`
                        <div style="display:flex;align-items:flex-start;padding:6px 0;border-bottom:1px solid #f5f5f5;gap:8px;">
                            <span style="color:#bbb;font-size:11px;min-width:56px;">${time}</span>
                            <span style="font-size:14px;">${icons[m.queue] || '📨'}</span>
                            <div style="flex:1;min-width:0;">
                                <div style="font-size:12px;color:#1890ff;font-weight:600;">${m.queue}</div>
                                <div style="font-size:11px;color:#666;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${bodyStr.substring(0, 80)}</div>
                            </div>
                        </div>
                    `);
                });
            } else {
                container.append(`
                    <div style="text-align:center;padding:40px 20px;color:#999;">
                        <div style="font-size:36px;">📬</div>
                        <div style="margin-top:8px;">No messages yet</div>
                        <div style="font-size:12px;">Classify an email to see messages flow</div>
                    </div>
                `);
            }
        } catch (e) {}
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