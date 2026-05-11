let paxosPage = 1;

async function loadPaxosPage() {
    const container = document.getElementById('page-paxos');
    container.innerHTML = `
        <div class="page-header">
            <h1>📜 Paxos共识日志</h1>
            <button class="btn btn-warning" onclick="runPaxosDemo()" style="margin-left:16px;">
                ⚡ Paxos 冲突演示
            </button>
        </div>
        <div id="paxos-demo-result" style="margin-bottom:16px"></div>
        <div class="card">
            <div id="paxos-logs"><div class="loading">加载中...</div></div>
        </div>
    `;
    fetchPaxosLogs();
}

async function runPaxosDemo() {
    const resultDiv = document.getElementById('paxos-demo-result');
    resultDiv.innerHTML = '<div class="card"><div class="loading">正在运行 Paxos 冲突演示...</div></div>';

    try {
        const result = await API.post('/api/paxos/demo-conflict', {});
        if (!result || !result.success) {
            resultDiv.innerHTML = `
                <div class="card" style="border-left:4px solid #ff4d4f;">
                    <strong>❌ 演示失败</strong>
                    <p>${result?.error || '未知错误'} (在线节点: ${result?.online_nodes || 0}/3)</p>
                    <p style="color:#888;">请确认 3 个 Acceptor 节点已启动 (端口 8503/8504/8505)</p>
                </div>`;
            return;
        }

        let html = '<div class="card" style="border-left:4px solid #1890ff;">';
        html += '<div class="card-title">⚡ Paxos 两阶段协议演示</div>';
        html += '<div class="paxos-timeline">';

        result.log.forEach(entry => {
            let cls = '';
            if (entry.message.includes('❌')) cls = 'fail';
            if (entry.message.includes('✅')) cls = 'success';
            if (entry.message.includes('⭐')) cls = '';
            if (entry.message.includes('🎯')) cls = 'success';
            if (entry.message.includes('🔒')) cls = '';
            if (entry.message.includes('【')) cls = 'phase-title';

            const isTitle = entry.message.startsWith('【');
            html += `<div class="paxos-event ${cls}" style="${isTitle ? 'font-weight:bold;margin-top:12px;padding:8px;background:#f0f5ff;border-radius:4px;' : ''}">
                <div class="msg">${entry.message}</div>
            </div>`;
        });

        html += '</div>';

        const rounds = result.rounds || [];
        html += '<div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap">';
        rounds.forEach(r => {
            const color = r.result === 'success' ? '#52c41a' : r.result === 'rejected' ? '#ff4d4f' : '#faad14';
            const label = r.result === 'success' ? '✅ 达成' : r.result === 'rejected' ? '❌ 被拒' : '⚠️ 失败';
            html += `<div class="badge" style="background:${color}15;border:1px solid ${color};padding:8px 16px;border-radius:8px;">
                <strong>ID=${r.id}</strong>: ${r.value} ${label}
            </div>`;
        });
        html += '</div></div>';

        resultDiv.innerHTML = html;
        fetchPaxosLogs();
    } catch (e) {
        resultDiv.innerHTML = `<div class="card" style="border-left:4px solid #ff4d4f;">
            <strong>❌ 请求失败: ${e.message}</strong></div>`;
    }
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
    html += App.renderPagination(data.total, data.page, data.limit, 'goPaxosPage');
    container.innerHTML = html;
}

function goPaxosPage(page) {
    paxosPage = page;
    fetchPaxosLogs();
}
