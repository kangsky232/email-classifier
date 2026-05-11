async function loadStatsPage() {
    const container = document.getElementById('page-stats');
    container.innerHTML = `
        <div class="page-header"><h1>📈 数据统计</h1></div>
        <div id="stats-overview" class="stats-grid"><div class="loading">加载中...</div></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div id="stats-categories" class="card"><div class="card-title">分类分布</div><div class="loading">加载中...</div></div>
            <div id="stats-trends" class="card"><div class="card-title">近7天趋势</div><div class="loading">加载中...</div></div>
        </div>
    `;
    fetchStats();
}

async function fetchStats() {
    const data = await api('/api/stats/overview');
    if (!data) return;
    
    const overview = data.overview || {};
    document.getElementById('stats-overview').innerHTML = `
        <div class="stat-card"><div class="label">邮件总数</div><div class="value">${overview.total_emails || 0}</div></div>
        <div class="stat-card"><div class="label">今日分类</div><div class="value">${overview.today_classified || 0}</div></div>
        <div class="stat-card"><div class="label">共识次数</div><div class="value">${overview.consensus_count || 0}</div></div>
        <div class="stat-card"><div class="label">分类结果数</div><div class="value">${overview.total_results || 0}</div></div>
    `;
    
    renderCategoryChart(data.categories || []);
    renderTrendChart(data.trends || []);
}

function renderCategoryChart(categories) {
    const container = document.getElementById('stats-categories');
    if (!categories.length) {
        container.innerHTML = '<div class="card-title">分类分布</div><div class="empty">暂无数据</div>';
        return;
    }
    
    const colors = ['#4facfe', '#ff4757', '#ffa502', '#2ed573', '#a55eea'];
    const total = categories.reduce((sum, c) => sum + c.count, 0);
    
    let gradParts = [];
    let current = 0;
    categories.forEach((c, i) => {
        const pct = (c.count / total) * 100;
        gradParts.push(`${colors[i % colors.length]} ${current}% ${current + pct}%`);
        current += pct;
    });
    
    let legendsHtml = categories.map((c, i) => `
        <div class="legend-item">
            <span class="legend-color" style="background:${colors[i % colors.length]}"></span>
            ${c.category}: ${c.count}
        </div>
    `).join('');
    
    container.innerHTML = `
        <div class="card-title">分类分布</div>
        <div class="pie-chart" style="background:conic-gradient(${gradParts.join(',')})"></div>
        <div class="legends">${legendsHtml}</div>
    `;
}

function renderTrendChart(trends) {
    const container = document.getElementById('stats-trends');
    if (!trends.length) {
        container.innerHTML = '<div class="card-title">近7天趋势</div><div class="empty">暂无数据</div>';
        return;
    }
    
    const max = Math.max(...trends.map(t => t.count), 1);
    
    let barsHtml = trends.map(t => {
        const height = Math.max((t.count / max) * 200, 20);
        const date = new Date(t.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
        return `<div class="chart-bar" style="height:${height}px">
            <span class="value">${t.count}</span>
            <span class="label">${date}</span>
        </div>`;
    }).join('');
    
    container.innerHTML = `
        <div class="card-title">近7天趋势</div>
        <div class="chart-container">${barsHtml}</div>
    `;
}
