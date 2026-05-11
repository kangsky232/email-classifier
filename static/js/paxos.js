let paxosPage = 1;

async function loadPaxosPage() {
    const container = document.getElementById('page-paxos');
    container.innerHTML = `
        <div class="page-header"><h1>📜 Paxos共识日志</h1></div>
        <div class="card">
            <div id="paxos-logs"><div class="loading">加载中...</div></div>
        </div>
    `;
    fetchPaxosLogs();
}

async function fetchPaxosLogs() {
    const data = await api(`/api/paxos/logs?page=${paxosPage}&limit=20`);
    if (!data) return;
    
    const container = document.getElementById('paxos-logs');
    if (!data.data || data.data.length === 0) {
        container.innerHTML = '<div class="empty">暂无Paxos日志</div>';
        return;
    }
    
    let html = `<table>
        <thead><tr><th>时间</th><th>邮件ID</th><th>阶段</th><th>提议者</th><th>提议值</th><th>结果</th></tr></thead>
        <tbody>`;
    
    data.data.forEach(log => {
        const time = new Date(log.created_at).toLocaleString('zh-CN');
        const resultClass = log.result === 'success' ? 'badge-success' : log.result === 'failed' ? 'badge-danger' : 'badge-info';
        html += `<tr>
            <td>${time}</td>
            <td>${log.email_id}</td>
            <td>${log.phase}</td>
            <td>${log.proposer || '-'}</td>
            <td>${log.value || '-'}</td>
            <td><span class="badge ${resultClass}">${log.result}</span></td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    html += renderPagination(data.total, data.page, data.limit, 'goPaxosPage');
    container.innerHTML = html;
}

function goPaxosPage(page) {
    paxosPage = page;
    fetchPaxosLogs();
}
