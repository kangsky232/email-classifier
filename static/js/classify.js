async function loadClassifyPage() {
    const container = document.getElementById('page-classify');
    container.innerHTML = `
        <div class="page-header"><h1>🤖 分类中心</h1></div>
        <div class="card">
            <div class="form-group">
                <label>发件人</label>
                <input type="text" id="classify-sender" placeholder="example@mail.com" value="boss@company.com">
            </div>
            <div class="form-group">
                <label>主题</label>
                <input type="text" id="classify-subject" placeholder="邮件主题" value="关于明天下午3点开会的通知">
            </div>
            <div class="form-group">
                <label>内容</label>
                <textarea id="classify-content" rows="4" placeholder="邮件内容">请各位同事明天下午3点准时到会议室参加项目进度汇报会</textarea>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" id="classify-btn" onclick="submitClassify()">🚀 提交分类</button>
                <button class="btn" onclick="clearClassifyForm()">📋 清空</button>
            </div>
        </div>
        <div id="classify-progress" style="display:none;">
            <div class="card">
                <div class="card-title">分类进度</div>
                <div id="progress-content"></div>
            </div>
        </div>
        <div id="classify-result"></div>
    `;
}

const ClassifyPage = {
    handleProgress(data) {
        const progressDiv = document.getElementById('classify-progress');
        const progressContent = document.getElementById('progress-content');
        if (!progressDiv || !progressContent) return;
        
        progressDiv.style.display = 'block';
        
        if (data.stage === 'started') {
            progressContent.innerHTML = `
                <div class="progress-step active">
                    <span class="progress-icon">⏳</span>
                    <span>${data.message}</span>
                </div>
            `;
        } else if (data.stage === 'completed') {
            progressContent.innerHTML = `
                <div class="progress-step completed">
                    <span class="progress-icon">✅</span>
                    <span>分类完成!</span>
                </div>
            `;
            setTimeout(() => {
                progressDiv.style.display = 'none';
            }, 2000);
        }
    }
};

function clearClassifyForm() {
    document.getElementById('classify-sender').value = '';
    document.getElementById('classify-subject').value = '';
    document.getElementById('classify-content').value = '';
    document.getElementById('classify-result').innerHTML = '';
    document.getElementById('classify-progress').style.display = 'none';
}

async function submitClassify() {
    const sender = document.getElementById('classify-sender').value;
    const subject = document.getElementById('classify-subject').value;
    const content = document.getElementById('classify-content').value;
    
    if (!content) { App.showToast('邮件内容不能为空', 'error'); return; }
    
    const btn = document.getElementById('classify-btn');
    btn.disabled = true;
    btn.textContent = '分类中...';
    document.getElementById('classify-result').innerHTML = '<div class="loading">正在分类，请稍候...</div>';
    document.getElementById('classify-progress').style.display = 'block';
    
    try {
        const result = await API.post('/api/classify', { sender, subject, content });
        
        btn.disabled = false;
        btn.textContent = '🚀 提交分类';
        document.getElementById('classify-progress').style.display = 'none';
        
        if (!result) return;
        displayClassifyResult(result);
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '🚀 提交分类';
        App.showToast('分类失败: ' + e.message, 'error');
    }
}

function displayClassifyResult(result) {
    const container = document.getElementById('classify-result');
    
    const categoryColors = {
        '工作': '#1890ff', '个人': '#52c41a', '广告': '#faad14',
        '垃圾': '#ff4d4f', '社交': '#722ed1', '财务': '#13c2c2',
        '技术支持': '#2f54eb', '其他': '#8c8c8c'
    };
    
    let agentsHtml = '';
    if (result.agents && result.agents.length > 0) {
        agentsHtml = `
            <div class="card">
                <div class="card-title">Agent投票详情</div>
                <div class="agent-votes-grid">
                    ${result.agents.map(a => {
                        const color = categoryColors[a.category] || '#8c8c8c';
                        const isRemote = a.is_remote ? ' <span class="badge badge-info">远程</span>' : '';
                        return `
                            <div class="agent-vote-card" style="border-left: 4px solid ${color};">
                                <div class="vote-header">
                                    <span class="agent-name">${a.agent_name}${isRemote}</span>
                                    <span class="vote-method">${a.method}</span>
                                </div>
                                <div class="vote-result" style="background: ${color}15;">
                                    <div class="vote-category" style="color: ${color}; font-weight: bold;">${a.category}</div>
                                    <div class="vote-confidence">
                                        <div class="confidence-bar">
                                            <div class="confidence-fill" style="width: ${(a.confidence * 100).toFixed(0)}%; background: ${color};"></div>
                                        </div>
                                        <span>${(a.confidence * 100).toFixed(1)}%</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }
    
    let paxosHtml = '';
    if (result.paxos_log && result.paxos_log.length > 0) {
        paxosHtml = `
            <div class="card">
                <div class="card-title">Paxos共识过程</div>
                <div class="paxos-timeline">
                    ${result.paxos_log.map(log => {
                        const resultClass = log.type === 'fail' ? 'fail' : log.type === 'learn' ? 'success' : '';
                        return `<div class="paxos-event ${resultClass}">
                            <div class="msg">${log.message}</div>
                        </div>`;
                    }).join('')}
                </div>
            </div>
        `;
    }
    
    const finalColor = categoryColors[result.final_category] || '#8c8c8c';
    const methodLabel = {
        'agent_consensus': 'Agent投票一致',
        'paxos_consensus': 'Paxos共识决策',
        'fallback': '降级处理'
    };
    
    container.innerHTML = `
        <div class="card result-card" style="border-top: 4px solid ${finalColor};">
            <div class="card-title">最终分类结果</div>
            <div class="final-result-display">
                <div class="result-category" style="color: ${finalColor}; font-size: 24px; font-weight: bold;">
                    ${result.final_category}
                </div>
                <div class="result-method">
                    <span class="badge badge-${result.method === 'paxos_consensus' ? 'warning' : 'success'}">
                        ${methodLabel[result.method] || result.method}
                    </span>
                </div>
                <div class="result-message">${result.message || ''}</div>
                ${result.elapsed_ms ? `<div class="result-time">Paxos耗时: ${result.elapsed_ms}ms</div>` : ''}
            </div>
        </div>
        ${agentsHtml}
        ${paxosHtml}
    `;
    
    App.showToast('分类完成');
}
