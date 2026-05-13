const ComparePage = {
    async render() {
        const page = document.getElementById('page-compare');
        page.innerHTML = `
            <div class="page-header">
                <h2>分类结果对比</h2>
                <div class="header-actions">
                    <select id="compare-email-select" class="form-control" onchange="ComparePage.loadComparison()">
                        <option value="">选择邮件查看对比...</option>
                    </select>
                </div>
            </div>
            <div id="compare-content">
                <div class="empty-state">
                    <div class="empty-icon">🔍</div>
                    <p>选择一封已分类的邮件查看各Agent的分类对比</p>
                </div>
            </div>
        `;
        await this.loadEmailList();
    },

    async loadEmailList() {
        try {
            const data = await API.get('/api/emails?limit=100');
            const select = document.getElementById('compare-email-select');
            const emails = data.data || [];
            const classified = emails.filter(e => e.final_category && e.final_category !== '未分类');
            
            if (classified.length === 0) {
                select.innerHTML = '<option value="">暂无已分类邮件</option>';
                return;
            }
            
            select.innerHTML = '<option value="">选择邮件查看对比...</option>' + 
                classified.map(e => `<option value="${e.id}">${e.subject || '(无主题)'} - ${e.sender}</option>`).join('');
        } catch (e) {
            console.error('加载邮件列表失败:', e);
        }
    },

    async loadComparison() {
        const emailId = document.getElementById('compare-email-select').value;
        if (!emailId) return;

        const content = document.getElementById('compare-content');
        content.innerHTML = '<div class="loading">加载对比数据...</div>';

        try {
            const data = await API.get(`/api/classify/${emailId}/result`);
            this.renderComparison(data);
        } catch (e) {
            content.innerHTML = `<div class="error-state">加载失败: ${e.message}</div>`;
        }
    },

    renderComparison(data) {
        const content = document.getElementById('compare-content');
        const { email, classifications, final_result, paxos_logs } = data;
        
        const categoryColors = {
            '工作': '#1890ff', '个人': '#52c41a', '广告': '#faad14',
            '垃圾': '#ff4d4f', '社交': '#722ed1', '财务': '#13c2c2',
            '技术支持': '#2f54eb', '其他': '#8c8c8c'
        };

        let html = `
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header"><h3>邮件信息</h3></div>
                <div class="card-body">
                    <div class="info-row"><span class="label">发件人:</span><span>${email.sender}</span></div>
                    <div class="info-row"><span class="label">主题:</span><span>${email.subject || '(无)'}</span></div>
                    <div class="info-row"><span class="label">内容:</span><span>${email.content?.substring(0, 200) || ''}...</span></div>
                </div>
            </div>
            
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header"><h3>Agent投票对比</h3></div>
                <div class="card-body">
                    <div class="agent-comparison-grid">
        `;

        const categories = {};
        classifications.forEach(c => {
            if (!categories[c.category]) categories[c.category] = [];
            categories[c.category].push(c);
        });

        classifications.forEach(c => {
            const isWinner = final_result && c.category === final_result.category;
            const color = categoryColors[c.category] || '#8c8c8c';
            html += `
                <div class="agent-vote-card ${isWinner ? 'winner' : ''}">
                    <div class="vote-header">
                        <span class="agent-name">${c.agent_name}</span>
                        <span class="vote-method">${c.method}</span>
                    </div>
                    <div class="vote-result" style="background: ${color}20; border-left: 4px solid ${color};">
                        <div class="vote-category" style="color: ${color};">${c.category}</div>
                        <div class="vote-confidence">
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: ${(c.confidence * 100).toFixed(0)}%; background: ${color};"></div>
                            </div>
                            <span>${(c.confidence * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    ${isWinner ? '<div class="winner-badge">✓ 最终结果</div>' : ''}
                </div>
            `;
        });

        html += `</div></div></div>`;

        html += `
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header"><h3>投票统计</h3></div>
                <div class="card-body">
                    <div class="vote-summary">
        `;

        Object.entries(categories).forEach(([cat, votes]) => {
            const color = categoryColors[cat] || '#8c8c8c';
            const isWinner = final_result && cat === final_result.category;
            html += `
                <div class="vote-summary-item ${isWinner ? 'winner' : ''}">
                    <div class="summary-color" style="background: ${color};"></div>
                    <div class="summary-info">
                        <div class="summary-category">${cat}</div>
                        <div class="summary-count">${votes.length} 票</div>
                    </div>
                    <div class="summary-bar">
                        <div class="summary-fill" style="width: ${(votes.length / classifications.length * 100).toFixed(0)}%; background: ${color};"></div>
                    </div>
                </div>
            `;
        });

        html += `</div></div></div>`;

        if (final_result) {
            html += `
                <div class="card result-card">
                    <div class="card-header"><h3>最终分类结果</h3></div>
                    <div class="card-body">
                        <div class="final-result-display">
                            <div class="result-category" style="color: ${categoryColors[final_result.category] || '#8c8c8c'};">
                                ${final_result.category}
                            </div>
                            <div class="result-method">
                                决策方式: <span class="badge badge-${final_result.method === 'paxos_consensus' ? 'warning' : 'success'}">
                                    ${final_result.method === 'paxos_consensus' ? 'Paxos共识' : 
                                      final_result.method === 'agent_consensus' ? 'Agent投票' : '降级处理'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        if (paxos_logs && paxos_logs.length > 0) {
            html += `
                <div class="card" style="margin-top: 20px;">
                    <div class="card-header"><h3>Paxos共识过程</h3></div>
                    <div class="card-body">
                        <div class="paxos-timeline">
            `;
            paxos_logs.forEach((log, i) => {
                html += `
                    <div class="timeline-item">
                        <div class="timeline-dot ${log.success ? 'success' : 'fail'}"></div>
                        <div class="timeline-content">
                            <div class="timeline-phase">阶段 ${i + 1}: ${log.phase}</div>
                            <div class="timeline-detail">
                                提议: ${log.proposal_number} | 
                                值: ${log.proposed_value} | 
                                接受者: ${log.acceptor_id}
                            </div>
                        </div>
                    </div>
                `;
            });
            html += `</div></div></div>`;
        }

        content.innerHTML = html;
    }
};
