const StatsPage = {
    async load() {
        const page = document.getElementById("page-stats");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Statistics</h2>
                    <p class="page-subtitle">Overview, category distribution, and recent trends.</p>
                </div>
                <button class="btn" type="button" onclick="StatsPage.load()">Refresh</button>
            </div>
            <div id="stats-content"></div>
        `;
        await this.fetchStats();
    },

    async fetchStats() {
        const box = document.getElementById("stats-content");
        App.setLoading(box, "Loading stats...");
        try {
            const result = await API.get("/api/stats/overview");
            this.render(result);
        } catch (error) {
            App.setError(box, error, () => this.fetchStats());
            App.showToast(error.message, "error");
        }
    },

    render(result) {
        const box = document.getElementById("stats-content");
        const overview = result.overview || {};
        const categories = result.categories || [];
        const trends = result.trends || [];
        box.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-label">Total emails</div><div class="stat-value">${overview.total_emails || 0}</div></div>
                <div class="stat-card"><div class="stat-label">Today classified</div><div class="stat-value">${overview.today_classified || 0}</div></div>
                <div class="stat-card"><div class="stat-label">Consensus count</div><div class="stat-value">${overview.consensus_count || 0}</div></div>
                <div class="stat-card"><div class="stat-label">Final results</div><div class="stat-value">${overview.total_results || 0}</div></div>
            </div>
            <div class="grid two">
                <div class="card">
                    <h3 class="card-title">Category Distribution</h3>
                    ${this.renderCategories(categories)}
                </div>
                <div class="card">
                    <h3 class="card-title">Recent Trend</h3>
                    ${this.renderTrends(trends)}
                </div>
            </div>
        `;
    },

    renderCategories(categories) {
        if (!categories.length) return App.empty("No category data");
        const total = categories.reduce((sum, item) => sum + Number(item.count || 0), 0) || 1;
        return `
            <div class="category-list">
                ${categories.map((item) => {
                    const count = Number(item.count || 0);
                    const width = Math.round((count / total) * 100);
                    return `
                        <div>
                            <div class="agent-head">
                                <span>${App.escape(item.category || "Unclassified")}</span>
                                <strong>${count}</strong>
                            </div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${width}%"></div></div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    },

    renderTrends(trends) {
        if (!trends.length) return App.empty("No trend data");
        const max = Math.max(...trends.map((item) => Number(item.count || 0)), 1);
        return `
            <div class="chart-bars">
                ${trends.map((item) => {
                    const count = Number(item.count || 0);
                    const height = Math.max((count / max) * 220, 18);
                    return `
                        <div class="chart-bar" style="height:${height}px">
                            <span class="value">${count}</span>
                            <span class="label">${App.escape(String(item.date || "").slice(5) || "-")}</span>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }
};
