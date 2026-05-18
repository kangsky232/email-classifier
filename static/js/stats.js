const StatsPage = {
    async load() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById("page-stats");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("stats.title")}</h2>
                    <p class="page-subtitle">${t("stats.subtitle")}</p>
                </div>
                <button class="btn" type="button" onclick="StatsPage.load()">${t("common.refresh")}</button>
            </div>
            <div id="stats-content"></div>
        `;
        await this.fetchStats();
    },

    async fetchStats() {
        const box = document.getElementById("stats-content");
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        App.setLoading(box, t("stats.loading"));
        try {
            const [overview, agentStats] = await Promise.all([
                API.get("/api/stats/overview"),
                API.get("/api/stats/agents")
            ]);
            this.render(overview, agentStats);
        } catch (error) {
            App.setError(box, error, () => this.fetchStats());
            App.showToast(error.message, "error");
        }
    },

    render(result, agentResult) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById("stats-content");
        const overview = result.overview || {};
        const categories = result.categories || [];
        const trends = result.trends || [];
        const agents = agentResult.agents || [];

        // Overview stats
        let html = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">${t("stats.total_emails")}</div>
                    <div class="stat-value">${overview.total_emails || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">${t("stats.today_classified")}</div>
                    <div class="stat-value">${overview.today_classified || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">${t("stats.consensus_count")}</div>
                    <div class="stat-value">${overview.consensus_count || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">${t("stats.total_results")}</div>
                    <div class="stat-value">${overview.total_results || 0}</div>
                </div>
            </div>
        `;

        // Category distribution + Agent performance
        html += `<div class="grid two" style="margin-bottom:16px;">`;

        // Category distribution with enhanced bar chart
        html += `
            <div class="card">
                <h3 class="card-title">${t("stats.category_dist")}</h3>
                ${this.renderCategoryChart(categories)}
            </div>
        `;

        // Agent performance comparison
        html += `
            <div class="card">
                <h3 class="card-title">${t("stats.agent_perf")}</h3>
                ${this.renderAgentPerformance(agents)}
            </div>
        `;

        html += `</div>`;

        // Trend chart + Method distribution
        html += `<div class="grid two">`;

        // Trend chart
        html += `
            <div class="card">
                <h3 class="card-title">${t("stats.trend")}</h3>
                ${this.renderTrends(trends)}
            </div>
        `;

        // Method distribution
        html += `
            <div class="card">
                <h3 class="card-title">${t("stats.method_dist")}</h3>
                ${this.renderMethodDistribution(categories, overview)}
            </div>
        `;

        html += `</div>`;

        box.innerHTML = html;
    },

    renderCategoryChart(categories) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!categories.length) return App.empty(t("stats.no_category_data"));
        const total = categories.reduce((sum, item) => sum + Number(item.count || 0), 0) || 1;
        const colors = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2", "#db2777"];
        const maxCount = Math.max(...categories.map(c => Number(c.count || 0)), 1);

        let html = `<div style="margin-bottom:12px;">`;
        html += categories.map((item, i) => {
            const count = Number(item.count || 0);
            const pct = ((count / total) * 100).toFixed(1);
            const barWidth = ((count / maxCount) * 100).toFixed(0);
            const color = colors[i % colors.length];
            return `
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
                        <span style="font-weight:600;color:${color};">${App.escape(item.category || "未分类")}</span>
                        <span style="color:#888;">${count} (${pct}%)</span>
                    </div>
                    <div style="height:10px;background:#f0f0f0;border-radius:5px;overflow:hidden;">
                        <div style="width:${barWidth}%;height:100%;background:${color};border-radius:5px;transition:width 0.6s;"></div>
                    </div>
                </div>
            `;
        }).join("");
        html += `</div>`;

        // Summary
        html += `
            <div style="font-size:11px;color:#888;padding:8px;background:#f9f9f9;border-radius:4px;">
                ${t("stats.total")}: <b>${total}</b> | ${t("email.category")}: <b>${categories.length}</b>
            </div>
        `;
        return html;
    },

    renderAgentPerformance(agents) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!agents.length) return App.empty(t("stats.no_agent_data"));

        const colors = { "llm_llm1": "#2563eb", "llm_llm2": "#16a34a", "llm_llm3": "#d97706", "llm_llm4": "#7c3aed" };
        const names = { "llm_llm1": "LLM1", "llm_llm2": "LLM2", "llm_llm3": "LLM3", "llm_llm4": "LLM4" };

        let html = `<div style="margin-bottom:12px;">`;

        // Accuracy bars
        html += `<div style="margin-bottom:14px;">
            <div style="font-size:12px;font-weight:600;margin-bottom:8px;color:#555;">${t("stats.accuracy")}</div>`;

        agents.forEach(agent => {
            const total = Number(agent.total || 0);
            const correct = Number(agent.correct || 0);
            const accuracy = total > 0 ? ((correct / total) * 100).toFixed(1) : 0;
            const color = colors[agent.method] || "#888";
            const name = names[agent.method] || agent.agent_name || agent.method;
            const barWidth = Math.max(accuracy, 2);

            html += `
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px;">
                        <span style="font-weight:600;color:${color};">${App.escape(name)}</span>
                        <span>${accuracy}% (${correct}/${total})</span>
                    </div>
                    <div style="height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">
                        <div style="width:${barWidth}%;height:100%;background:${color};border-radius:4px;"></div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;

        // Average confidence
        html += `<div>
            <div style="font-size:12px;font-weight:600;margin-bottom:8px;color:#555;">${t("stats.avg_confidence")}</div>`;

        agents.forEach(agent => {
            const avgConf = Number(agent.avg_confidence || 0);
            const confPct = (avgConf * 100).toFixed(1);
            const color = colors[agent.method] || "#888";
            const name = names[agent.method] || agent.agent_name || agent.method;
            const barWidth = Math.max(confPct, 2);

            html += `
                <div style="margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px;">
                        <span style="font-weight:600;color:${color};">${App.escape(name)}</span>
                        <span>${confPct}%</span>
                    </div>
                    <div style="height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">
                        <div style="width:${barWidth}%;height:100%;background:${color};border-radius:4px;"></div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;

        html += `</div>`;
        return html;
    },

    renderTrends(trends) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!trends.length) return App.empty(t("stats.no_trend_data"));
        const max = Math.max(...trends.map((item) => Number(item.count || 0)), 1);
        const chartHeight = 180;

        let html = `<div style="display:flex;align-items:end;gap:6px;height:${chartHeight}px;padding:8px 4px 24px;position:relative;">`;

        // Y-axis labels
        html += `<div style="position:absolute;left:0;top:0;bottom:24px;display:flex;flex-direction:column;justify-content:space-between;font-size:9px;color:#999;width:24px;">
            <span>${max}</span>
            <span>${Math.round(max / 2)}</span>
            <span>0</span>
        </div>`;

        // Bars
        html += `<div style="display:flex;align-items:end;gap:6px;flex:1;margin-left:28px;height:100%;">`;
        trends.map((item) => {
            const count = Number(item.count || 0);
            const height = Math.max((count / max) * (chartHeight - 40), 4);
            const dateStr = String(item.date || "").slice(5) || "-";
            return `
                <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:end;height:100%;">
                    <div style="font-size:10px;font-weight:700;color:#2563eb;margin-bottom:4px;">${count}</div>
                    <div style="width:100%;max-width:40px;height:${height}px;background:linear-gradient(180deg,#3b82f6,#2563eb);border-radius:4px 4px 0 0;min-height:4px;"></div>
                    <div style="font-size:9px;color:#888;margin-top:4px;white-space:nowrap;">${App.escape(dateStr)}</div>
                </div>
            `;
        }).join("");
        html += `</div></div>`;

        return html;
    },

    renderMethodDistribution(categories, overview) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const total = Number(overview.total_results || 0);
        if (total === 0) return App.empty(t("stats.no_method_data"));

        const methods = [
            { name: t("stats.method_majority"), color: "#2563eb", desc: "3 LLM Agent" },
            { name: t("stats.method_paxos"), color: "#7c3aed", desc: "Paxos" }
        ];

        let html = `<div style="margin-bottom:12px;">`;
        html += methods.map(m => `
            <div style="display:flex;align-items:center;gap:10px;padding:10px;margin-bottom:6px;border-radius:6px;background:#f8f9fa;border-left:3px solid ${m.color};">
                <div style="width:10px;height:10px;border-radius:50%;background:${m.color};flex-shrink:0;"></div>
                <div>
                    <div style="font-size:13px;font-weight:600;">${m.name}</div>
                    <div style="font-size:11px;color:#888;">${m.desc}</div>
                </div>
            </div>
        `).join("");
        html += `</div>`;

        html += `
            <div style="font-size:11px;color:#888;padding:8px;background:#f9f9f9;border-radius:4px;">
                ${t("stats.flow_desc")}
            </div>
        `;

        return html;
    }
};
