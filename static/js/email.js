let emailPage = 1;
let emailSearch = '';
let emailCategory = '';
let selectedEmails = new Set();

async function loadEmailPage() {
    const container = document.getElementById('page-email');
    container.innerHTML = `
        <div class="page-header">
            <h1>📧 邮件管理</h1>
            <div class="header-actions">
                <button class="btn btn-success" onclick="showCreateEmailModal()">+ 新建邮件</button>
            </div>
        </div>
        <div class="card">
            <div class="search-bar">
                <input type="text" id="email-search" placeholder="搜索发件人、主题、内容..." value="${emailSearch}">
                <select id="email-category-filter">
                    <option value="">全部分类</option>
                    <option value="工作">工作</option>
                    <option value="个人">个人</option>
                    <option value="广告">广告</option>
                    <option value="垃圾">垃圾</option>
                    <option value="社交">社交</option>
                    <option value="财务">财务</option>
                    <option value="技术支持">技术支持</option>
                </select>
                <button class="btn btn-primary" onclick="searchEmails()">搜索</button>
            </div>
            <div class="batch-bar" id="batch-bar" style="display:none;">
                <span id="selected-count">0</span> 封邮件已选
                <button class="btn btn-sm btn-primary" onclick="batchClassify()">批量分类</button>
                <button class="btn btn-sm btn-danger" onclick="batchDelete()">批量删除</button>
                <button class="btn btn-sm" onclick="clearSelection()">取消选择</button>
            </div>
            <div id="email-table"><div class="loading">加载中...</div></div>
        </div>
    `;
    document.getElementById('email-category-filter').value = emailCategory;
    document.getElementById('email-search').addEventListener('keyup', (e) => {
        if (e.key === 'Enter') searchEmails();
    });
    fetchEmails();
}

async function fetchEmails() {
    const data = await API.get(`/api/emails?page=${emailPage}&limit=10&search=${emailSearch}&category=${emailCategory}`);
    if (!data) return;
    
    const container = document.getElementById('email-table');
    if (!data.data || data.data.length === 0) {
        container.innerHTML = '<div class="empty">暂无邮件数据</div>';
        return;
    }
    
    let html = `<table>
        <thead><tr>
            <th><input type="checkbox" onchange="toggleAllEmails(this)" ${selectedEmails.size > 0 ? 'checked' : ''}></th>
            <th>ID</th><th>发件人</th><th>主题</th><th>分类</th><th>置信度</th><th>时间</th><th>操作</th>
        </tr></thead>
        <tbody>`;
    
    data.data.forEach(e => {
        const category = e.final_category || '未分类';
        const badgeClass = getBadgeClass(category);
        const time = new Date(e.created_at).toLocaleString('zh-CN');
        const confidence = e.confidence ? (e.confidence * 100).toFixed(1) + '%' : '-';
        const isChecked = selectedEmails.has(e.id) ? 'checked' : '';
        html += `<tr class="${selectedEmails.has(e.id) ? 'selected' : ''}">
            <td><input type="checkbox" ${isChecked} onchange="toggleEmailSelect(${e.id}, this)"></td>
            <td>${e.id}</td>
            <td>${e.sender}</td>
            <td>${e.subject || '-'}</td>
            <td><span class="badge ${badgeClass}">${category}</span></td>
            <td>${confidence}</td>
            <td>${time}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="viewEmailDetail(${e.id})">详情</button>
                <button class="btn btn-sm btn-warning" onclick="classifySingleEmail(${e.id})">分类</button>
                <button class="btn btn-sm btn-danger" onclick="deleteEmail(${e.id})">删除</button>
            </td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    html += App.renderPagination(data.total, data.page, data.limit, 'goEmailPage');
    container.innerHTML = html;
    updateBatchBar();
}

function toggleEmailSelect(id, checkbox) {
    if (checkbox.checked) {
        selectedEmails.add(id);
    } else {
        selectedEmails.delete(id);
    }
    updateBatchBar();
}

function toggleAllEmails(checkbox) {
    const rows = document.querySelectorAll('#email-table tbody tr');
    rows.forEach(row => {
        const cb = row.querySelector('input[type="checkbox"]');
        const id = parseInt(cb.getAttribute('onchange').match(/\d+/)[0]);
        if (checkbox.checked) {
            selectedEmails.add(id);
            cb.checked = true;
            row.classList.add('selected');
        } else {
            selectedEmails.delete(id);
            cb.checked = false;
            row.classList.remove('selected');
        }
    });
    updateBatchBar();
}

function clearSelection() {
    selectedEmails.clear();
    fetchEmails();
}

function updateBatchBar() {
    const bar = document.getElementById('batch-bar');
    const count = document.getElementById('selected-count');
    if (bar && count) {
        bar.style.display = selectedEmails.size > 0 ? 'flex' : 'none';
        count.textContent = selectedEmails.size;
    }
}

async function batchClassify() {
    if (selectedEmails.size === 0) return;
    App.showToast(`正在批量分类 ${selectedEmails.size} 封邮件...`);
    
    try {
        const result = await API.post('/api/emails/batch', {
            action: 'classify',
            email_ids: Array.from(selectedEmails)
        });
        
        if (result) {
            const successCount = result.results.filter(r => r.success).length;
            App.showToast(`批量分类完成: ${successCount}/${result.total} 成功`);
            selectedEmails.clear();
            fetchEmails();
        }
    } catch (e) {
        App.showToast('批量分类失败: ' + e.message, 'error');
    }
}

async function batchDelete() {
    if (selectedEmails.size === 0) return;
    if (!confirm(`确定删除选中的 ${selectedEmails.size} 封邮件？`)) return;
    
    try {
        const result = await API.post('/api/emails/batch', {
            action: 'delete',
            email_ids: Array.from(selectedEmails)
        });
        
        if (result) {
            const successCount = result.results.filter(r => r.success).length;
            App.showToast(`批量删除完成: ${successCount}/${result.total} 成功`);
            selectedEmails.clear();
            fetchEmails();
        }
    } catch (e) {
        App.showToast('批量删除失败: ' + e.message, 'error');
    }
}

async function classifySingleEmail(emailId) {
    App.showToast('正在分类...');
    try {
        const email = await API.get(`/api/emails/${emailId}`);
        if (!email || !email.email) return;
        
        const result = await API.post('/api/classify', {
            sender: email.email.sender,
            subject: email.email.subject,
            content: email.email.content
        });
        
        if (result && result.success) {
            App.showToast(`分类完成: ${result.final_category}`);
            fetchEmails();
        } else {
            App.showToast('分类失败', 'error');
        }
    } catch (e) {
        App.showToast('分类失败: ' + e.message, 'error');
    }
}

function getBadgeClass(category) {
    const map = {
        '工作': 'badge-primary', '个人': 'badge-success', '广告': 'badge-warning',
        '垃圾': 'badge-danger', '社交': 'badge-info', '财务': 'badge-purple',
        '技术支持': 'badge-primary', '其他': 'badge-secondary'
    };
    return map[category] || 'badge-info';
}

function searchEmails() {
    emailSearch = document.getElementById('email-search').value;
    emailCategory = document.getElementById('email-category-filter').value;
    emailPage = 1;
    fetchEmails();
}

function goEmailPage(page) {
    emailPage = page;
    fetchEmails();
}

function showCreateEmailModal() {
    App.showModal(`
        <div class="modal-header">
            <h3>新建邮件</h3>
            <button class="modal-close" onclick="App.closeModal()">&times;</button>
        </div>
        <div class="form-group">
            <label>发件人</label>
            <input type="text" id="new-email-sender" placeholder="example@mail.com">
        </div>
        <div class="form-group">
            <label>主题</label>
            <input type="text" id="new-email-subject" placeholder="邮件主题">
        </div>
        <div class="form-group">
            <label>内容</label>
            <textarea id="new-email-content" rows="5" placeholder="邮件内容"></textarea>
        </div>
        <div class="btn-group">
            <button class="btn btn-primary" onclick="createEmail()">提交</button>
            <button class="btn" onclick="App.closeModal()">取消</button>
        </div>
    `);
}

async function createEmail() {
    const sender = document.getElementById('new-email-sender').value;
    const subject = document.getElementById('new-email-subject').value;
    const content = document.getElementById('new-email-content').value;
    
    if (!sender) { App.showToast('发件人不能为空', 'error'); return; }
    
    try {
        const result = await API.post('/api/emails', { sender, subject, content });
        if (result && result.success) {
            App.closeModal();
            App.showToast('邮件创建成功');
            fetchEmails();
        }
    } catch (e) {
        App.showToast('创建失败: ' + e.message, 'error');
    }
}

async function viewEmailDetail(emailId) {
    try {
        const data = await API.get(`/api/emails/${emailId}`);
        if (!data) return;
        
        const e = data.email;
        const classifications = data.classifications || [];
        const finalResult = data.final_result;
        const paxosLogs = data.paxos_logs || [];
        
        let classHtml = classifications.map(c => `
            <tr>
                <td>${c.agent_name}</td>
                <td>${c.method}</td>
                <td><span class="badge ${getBadgeClass(c.category)}">${c.category}</span></td>
                <td>${(c.confidence * 100).toFixed(1)}%</td>
            </tr>
        `).join('');
        
        let paxosHtml = paxosLogs.map(log => {
            const time = new Date(log.created_at).toLocaleString('zh-CN');
            return `<div class="paxos-event">
                <div class="time">${time}</div>
                <div class="msg">[${log.phase}] 提议${log.proposal_number}: ${log.proposed_value} → ${log.result}</div>
            </div>`;
        }).join('');
        
        App.showModal(`
            <div class="modal-header">
                <h3>邮件详情 #${e.id}</h3>
                <button class="modal-close" onclick="App.closeModal()">&times;</button>
            </div>
            <div class="detail-section">
                <div class="detail-row"><span class="detail-label">发件人:</span><span class="detail-value">${e.sender}</span></div>
                <div class="detail-row"><span class="detail-label">主题:</span><span class="detail-value">${e.subject || '-'}</span></div>
                <div class="detail-row"><span class="detail-label">内容:</span><span class="detail-value">${e.content || '-'}</span></div>
                ${finalResult ? `<div class="detail-row"><span class="detail-label">最终分类:</span><span class="detail-value"><span class="badge ${getBadgeClass(finalResult.category)}">${finalResult.category}</span> (${finalResult.method})</span></div>` : ''}
            </div>
            ${classifications.length > 0 ? `
            <h4 style="margin:16px 0 8px">Agent分类结果</h4>
            <table><thead><tr><th>Agent</th><th>方法</th><th>分类</th><th>置信度</th></tr></thead>
            <tbody>${classHtml}</tbody></table>` : ''}
            ${paxosLogs.length > 0 ? `
            <h4 style="margin:16px 0 8px">Paxos共识过程</h4>
            <div class="paxos-timeline">${paxosHtml}</div>` : ''}
        `);
    } catch (e) {
        App.showToast('加载详情失败: ' + e.message, 'error');
    }
}

async function deleteEmail(id) {
    if (!confirm('确定删除该邮件？')) return;
    try {
        const result = await API.delete(`/api/emails/${id}`);
        if (result && result.success) {
            App.showToast('删除成功');
            fetchEmails();
        }
    } catch (e) {
        App.showToast('删除失败: ' + e.message, 'error');
    }
}
