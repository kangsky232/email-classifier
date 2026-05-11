async function loadMonitorPage() {
    const container = document.getElementById('page-monitor');
    container.innerHTML = `
        <div class="page-header"><h1>📊 Agent监控</h1></div>
        <div id="agent-cards"><div class="loading">加载中...</div></div>
        <div id="queue-status" style="margin-top:24px"></div>
    `;
    fetchAgentStatus();
    fetchQueueStatus();
}

async function fetchAgentStatus() {
    const data = await api('/api/agents/status');
    if (!data || !data.agents) return;
    
    const container = document.getElementById('agent-cards');
    let html = '';
    
    data.agents.forEach(agent => {
        const statusClass = agent.status === 'online' ? 'online' : 'offline';
        html += `
        <div class="card agent-card">
            <div class="header">
                <span class="name">${agent.name}</span>
                <span class="status ${statusClass}"></span>
            </div>
            <div class="detail">算法: ${agent.method}</div>
            <div class="detail">已处理: ${agent.processed_count}</div>
            <div class="detail">平均耗时: ${agent.avg_time_ms}ms</div>
        </div>`;
    });
    
    container.innerHTML = html;
}

async function fetchQueueStatus() {
    const data = await api('/api/queue/status');
    if (!data) return;
    
    const container = document.getElementById('queue-status');
    const queues = data.queues || [];
    
    let html = `<div class="card">
        <div class="card-title">消息队列状态</div>
        <table>
            <thead><tr><th>队列名</th><th>待处理</th><th>消费者数</th></tr></thead>
            <tbody>`;
    
    queues.forEach(q => {
        html += `<tr>
            <td>${q.name}</td>
            <td>${q.messages}</td>
            <td>${q.consumers}</td>
        </tr>`;
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}
