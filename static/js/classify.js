const ClassifyPage = {
    load() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById("page-classify");
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("classify.title")}</h2>
                    <p class="page-subtitle">${t("classify.subtitle")}</p>
                </div>
            </div>
            <div class="grid two">
                <div class="card">
                    <h3 class="card-title">${t("classify.input")}</h3>
                    <div class="form-grid">
                        <div class="form-group"><label>${t("classify.sender")}</label><input id="classify-sender" placeholder="zhangwei@company.com"></div>
                        <div class="form-group"><label>${t("classify.subject")}</label><input id="classify-subject" placeholder="项目进度会议通知"></div>
                        <div class="form-group"><label>${t("classify.content")}</label><textarea id="classify-content" style="min-height:120px;" placeholder="${t("classify.content_required")}"></textarea></div>
                    </div>
                    <div class="form-actions">
                        <button class="btn" type="button" onclick="ClassifyPage.clear()">${t("classify.clear")}</button>
                        <button class="btn" type="button" onclick="ClassifyPage.generateRandom()">${t("classify.random_test")}</button>
                        <button id="classify-submit" class="btn btn-primary" type="button" onclick="ClassifyPage.submit()">${t("classify.submit")}</button>
                    </div>
                </div>
                <div id="classify-result" class="card">
                    <h3 class="card-title">${t("classify.result")}</h3>
                    <div class="empty-state">${t("classify.result_hint")}</div>
                </div>
            </div>
        `;
    },

    generateRandom() {
        const randomEmails = [
            // === 正常邮件（20条）===
            { sender: "hr@company.com", subject: "年度体检通知", content: "各位同事：\n\n公司将于下周组织年度体检，请各位按时参加。\n时间：周一至周五 9:00-17:00\n地点：公司一楼医务室\n\n请携带工牌。" },
            { sender: "it@company.com", subject: "系统维护通知", content: "尊敬的用户：\n\n系统将于今晚22:00-次日6:00进行维护，届时部分服务可能暂停。\n\n请提前保存工作内容。" },
            { sender: "promo@cheap-deals.cn", subject: "限时特惠！全场5折", content: "尊敬的会员：\n\n本店周年庆，全场商品5折起！\n活动时间：仅限今日\n\n立即抢购：http://fake-sale.com" },
            { sender: "security@bank-verify.cn", subject: "【紧急】账户异常登录", content: "尊敬的客户：\n\n检测到您的账户在异地登录，为保障安全，请立即验证：\nhttp://fake-bank.com/verify\n\n如非本人操作，请立即修改密码。" },
            { sender: "team@company.com", subject: "项目进度周报", content: "各位：\n\n本周完成：\n1. 用户模块开发完成\n2. API接口联调完成\n3. 单元测试覆盖率85%\n\n下周计划：\n1. 性能优化\n2. 文档编写" },
            { sender: "lucky@prize-win.com", subject: "恭喜您中奖100万！", content: "尊敬的用户：\n\n恭喜您被随机抽中为幸运用户，奖金100万元！\n\n请立即联系客服领取：400-xxx-xxxx\n活动有效期24小时。" },
            { sender: "alert@monitoring.com", subject: "[告警] 服务器CPU使用率超过90%", content: "告警详情：\n- 服务器：web-prod-03\n- 指标：CPU使用率\n- 当前值：95%\n- 阈值：90%\n- 时间：2026-05-18 14:32:00\n\n请及时处理。" },
            { sender: "scammer@crypto-profit.io", subject: "每天躺赚1000U！", content: "兄弟你好！\n\n我之前也是打工仔，后来接触到加密货币量化交易，现在每天稳定收入1000U+。\n\n只需要：\n1. 注册账户\n2. 充值100U起\n3. 开启AI自动交易\n\n加我微信：crypto888 详细了解" },
            { sender: "phishing@amazon-security.com", subject: "Your Amazon account is locked", content: "Dear Customer,\n\nWe have detected unusual activity on your Amazon account.\nYour account has been temporarily locked.\n\nPlease verify your identity immediately:\nhttp://fake-amazon.com/verify\n\nFailure to verify within 24 hours will result in permanent account suspension.\n\nAmazon Security Team" },
            { sender: "gitlab@company.com", subject: "Pipeline Failed: backend/main", content: "Pipeline #58923 failed\n\nBranch: main\nCommit: fix: resolve null pointer in user service\nStage: test\nJob: unit-test\n\nFailed tests:\n- test_user_login (test_auth.py)\n- test_token_refresh (test_auth.py)\n\nView details: https://gitlab.company.com/pipeline/58923" },
            { sender: "no-reply@wechat.com", subject: "微信支付账单通知", content: "微信支付消费通知\n\n金额：￥158.00\n商户：美团外卖\n时间：2026-05-18 12:30\n\n如非本人操作，请立即联系客服。" },
            { sender: "wang.fang@company.com", subject: "请假申请", content: "领导您好：\n\n因家中有事，申请5月20日-5月22日请假3天。\n工作已交接给李明。\n\n请批准，谢谢！" },
            { sender: "sale@fake-electronics.com", subject: "iPhone 16 Pro 仅售2999元", content: "限时抢购！\n\niPhone 16 Pro 国行全新未拆封\n原价：8999元\n现价：2999元（仅限前100名）\n\n支持货到付款，7天无理由退换\n抢购链接：http://fake-electronics.com/iphone" },
            { sender: "info@newsletter-tech.com", subject: "Tech Weekly #256", content: "本周技术热点：\n\n1. OpenAI发布GPT-5，性能提升40%\n2. Kubernetes 1.30发布\n3. Rust语言进入Linux内核开发\n\n阅读全文：https://tech-weekly.com/256\n退订：https://tech-weekly.com/unsub" },
            { sender: "no-reply@aliyun.com", subject: "阿里云服务器异常告警", content: "【阿里云监控告警】\n\n实例ID：i-xxx12345\n告警规则：CPU使用率>85%\n当前值：92%\n触发时间：2026-05-18 15:23\n\n请登录控制台查看。" },
            { sender: "delivery@sf-express.com", subject: "顺丰快递派件通知", content: "您的快递已发出：\n运单号：SF1234567890\n物品：文件\n预计送达：今天18:00前\n\n快递员：王师傅 138****5678\n请保持电话畅通。" },
            { sender: "scammer@apple-id-verify.com", subject: "Apple: Your Apple ID has been locked", content: "Dear Apple User,\n\nYour Apple ID has been locked due to too many failed sign-in attempts.\n\nTo unlock your account, verify your identity:\nhttp://fake-apple.com/unlock\n\nApple Support" },
            { sender: "tel@fake-10086.com", subject: "【中国移动】积分即将清零", content: "尊敬的用户：\n\n您有8650积分将于本月底清零。\n可兑换话费、流量或实物礼品。\n\n立即兑换：http://fake-10086.com/exchange\n退订回复0000" },
            { sender: "intern@company.com", subject: "实习周报 - 第4周", content: "导师您好：\n\n本周工作内容：\n1. 完成了用户模块的单元测试编写\n2. 学习了Docker容器化部署\n3. 参与了代码审查\n\n下周计划：\n1. 开始开发消息通知功能\n2. 学习CI/CD流程\n\n请指导，谢谢！" },
            { sender: "bonus@casino-royal.com", subject: "新用户注册送888元", content: "恭喜您获得888元新手礼包！\n\n首充100送100\n每日签到领红包\nVIP专属返水最高3%\n\n立即注册：http://fake-casino.com/reg\n（本活动最终解释权归平台所有）" },
            // === 边界邮件：容易引发 Agent 分歧，触发 Paxos 不同分支 ===
            { sender: "events@tech-vendor.com", subject: "免费AI技术研讨会邀请", content: "尊敬的客户：\n\n诚邀您参加我们举办的AI技术研讨会，主题：大模型在企业中的落地实践。\n时间：本周五 14:00\n地点：线上Zoom\n费用：免费\n\n前50名报名者赠送《AI实战指南》一本。\n立即报名：https://tech-vendor.com/ai-seminar\n\n（是工作相关的技术分享，还是营销推广？）" },
            { sender: "ceo@company.com", subject: "员工专属福利 - 团购优惠", content: "各位同事：\n\n公司为大家争取到了合作伙伴的专属福利：\n- iPhone 16 Pro 员工价 ￥6,999（市价 ￥8,999）\n- 戴森吹风机 员工价 ￥2,199\n- 限量100台，先到先得\n\n有意者请在OA提交申请。\n\n（是公司福利通知，还是变相推销？）" },
            { sender: "security@company.com", subject: "【紧急】请立即修改密码", content: "检测到您的账号存在异常登录行为。\n\n来源IP：103.xxx.xxx.78（越南）\n时间：2026-05-18 03:22\n\n请在24小时内修改密码，否则账号将被锁定。\n修改链接：https://company.com/change-password\n\n如非本人操作请联系IT。\n\n（是真实安全告警，还是钓鱼邮件？）" },
            { sender: "wang.jun@company.com", subject: "Re: Re: 项目方案", content: "我觉得可以，你看着办吧。\n\n--- 原始邮件 ---\n发件人: zhang.wei@company.com\n我觉得B方案更好，成本低20%。\n\n--- 原始邮件 ---\n发件人: wang.jun@company.com\nA方案和B方案各有什么优劣？\n\n（邮件链缺少上下文，难以判断具体类别）" },
            { sender: "no-reply@company.com", subject: "通知", content: "请查收附件。\n\n（内容过于简短，无法判断类别）" },
            { sender: "marketing@company.com", subject: "技术白皮书下载 - 云原生架构最佳实践", content: "您好：\n\n我们最新发布了《云原生架构最佳实践》白皮书，涵盖：\n- 微服务设计模式\n- Kubernetes生产部署\n- 可观测性建设\n\n免费下载：https://vendor.com/whitepaper\n\n填写问卷还可获得一对一技术咨询机会。\n\n（是技术资料分享，还是营销获客？）" },
            { sender: "hr@company.com", subject: "团建活动投票", content: "各位同事：\n\n下季度团建活动方案投票：\nA. 户外拓展（2天1夜）\nB. 密室逃脱 + 聚餐\nC. 剧本杀 + KTV\nD. 自由活动（发200元补贴）\n\n请在本周五前在OA投票。\n\n注意：如选择A，请确认身体条件适合户外活动。\n\n（是HR通知、活动组织，还是行政事务？）" },
            { sender: "colleague@company.com", subject: "帮我看看这个bug", content: "Hey，\n\n我这边跑测试一直报错，你帮我看看呗：\nTypeError: Cannot read property 'id' of undefined\nat UserService.getUser (user.js:42)\n\n感觉是数据库查询返回了null，但我不确定。\n\nThx!\n\n（是技术讨论、工作协作，还是IT支持请求？）" },
            { sender: "newsletter@medium.com", subject: "Top stories for you: AI, Cloud, and DevOps", content: "Your weekly digest:\n\n1. How We Scaled to 1M Users with Kubernetes\n2. The Future of Serverless Computing\n3. Why Every Developer Should Learn Rust\n4. Building Resilient Microservices\n\nRead more on Medium\nUnsubscribe: https://medium.com/unsub\n\n（是技术资讯订阅，还是营销邮件？）" },
            { sender: "client@big-corp.com", subject: "合作提案 - 请尽快回复", content: "张总您好：\n\n我们对贵司的邮件分类产品很感兴趣，希望探讨合作可能。\n\n初步想法：\n1. 技术集成（API对接）\n2. 联合解决方案\n3. OEM授权\n\n方便的话本周约个电话？我们下周要做技术选型决策。\n\nBest regards,\n李明 | 大客户部\n\n（是商务合作、销售线索，还是客户支持？）" }
        ];

        const email = randomEmails[Math.floor(Math.random() * randomEmails.length)];
        document.getElementById("classify-sender").value = email.sender;
        document.getElementById("classify-subject").value = email.subject;
        document.getElementById("classify-content").value = email.content;
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        App.showToast(t("classify.random_filled"));
    },

    clear() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        document.getElementById("classify-sender").value = "";
        document.getElementById("classify-subject").value = "";
        document.getElementById("classify-content").value = "";
        document.getElementById("classify-result").innerHTML = `
            <h3 class="card-title">${t("classify.result")}</h3>
            <div class="empty-state">${t("classify.result_hint")}</div>
        `;
    },

    async submit() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const sender = document.getElementById("classify-sender").value.trim() || "unknown";
        const subject = document.getElementById("classify-subject").value.trim();
        const content = document.getElementById("classify-content").value.trim();
        const button = document.getElementById("classify-submit");
        const box = document.getElementById("classify-result");
        if (!content) {
            App.showToast(t("classify.content_required"), "warning");
            return;
        }
        if (content.length > 10000) {
            App.showToast(t("classify.content_too_long"), "warning");
            return;
        }
        button.disabled = true;
        App.setLoading(box, t("classify.classifying"));
        try {
            const result = await API.post("/api/classify", { sender, subject, content });
            this.renderResult(result);
            App.showToast(t("classify.complete"));
        } catch (error) {
            App.setError(box, error, () => this.submit());
            App.showToast(error.message, "error");
        } finally {
            button.disabled = false;
        }
    },

    renderResult(result) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById("classify-result");
        if (!result.success) {
            App.setError(box, result.message || t("common.error"));
            return;
        }
        const agents = result.agents || [];
        const votes = result.votes || [];
        const paxosLog = result.paxos_log || [];

        let html = `
            <h3 class="card-title">${t("classify.result")}</h3>
            <div class="result-hero">
                <div class="completion-animation" aria-label="Classification completed">
                    <div class="completion-ring"><span class="completion-check">✓</span></div>
                    <div class="completion-pulse"></div>
                </div>
                <div>
                    <div class="stat-label">${t("classify.final_result")}</div>
                    <div class="stat-value">${App.escape(result.final_category || "-")}</div>
                </div>
                <div class="text-muted">${t("classify.method")}: ${App.escape(this.methodLabel(result.method || "-"))}${result.email_id ? ` | ${t("email.detail")} #${result.email_id}` : ""}</div>
                ${result.message ? `<p style="font-size:12px;color:#666;">${App.escape(result.message)}</p>` : ""}
            </div>
        `;

        html += `<h4 style="margin-top:16px;">${t("classify.agent_results")}</h4>`;
        html += this.renderAgentResults(agents);

        if (votes.length > 0) {
            html += `<h4 style="margin-top:16px;">${t("classify.paxos_vote")}</h4>`;
            html += this.renderVotes(votes, result.final_category);
        }

        if (paxosLog.length) {
            html += `<h4 style="margin-top:16px;">${t("classify.paxos_process")}</h4>`;
            html += this.renderPaxos(paxosLog);
        }

        box.innerHTML = html;
    },

    methodLabel(method) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const labels = {
            "paxos_consensus": t("classify.paxos_consensus"),
            "majority_vote": t("classify.majority_vote")
        };
        return labels[method] || method;
    },

    renderAgentResults(agents) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!agents.length) return App.empty(t("classify.no_agent_results"));

        const validAgents = agents.filter(a => a.category && a.category !== "错误");

        let html = `
            <div style="overflow-x:auto;margin-bottom:12px;">
                <table style="width:100%;font-size:12px;border-collapse:collapse;">
                    <tr style="background:#f5f5f5;">
                        <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;">Agent</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #ddd;">${t("email.category")}</th>
                        <th style="padding:8px;text-align:center;border-bottom:2px solid #ddd;">${t("stats.avg_confidence")}</th>
                        <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;">${t("classify.method")}</th>
                    </tr>
                    ${validAgents.map(a => {
                        const conf = ((a.confidence || 0) * 100).toFixed(1);
                        return `
                            <tr style="border-bottom:1px solid #f0f0f0;">
                                <td style="padding:8px;"><strong>${App.escape(a.agent_name || "-")}</strong></td>
                                <td style="padding:8px;text-align:center;">${App.badge(a.category)}</td>
                                <td style="padding:8px;text-align:center;">
                                    <div style="display:flex;align-items:center;gap:4px;justify-content:center;">
                                        <div style="width:50px;height:6px;background:#eee;border-radius:3px;overflow:hidden;">
                                            <div style="width:${conf}%;height:100%;background:#2563eb;border-radius:3px;"></div>
                                        </div>
                                        <span style="font-size:11px;">${conf}%</span>
                                    </div>
                                </td>
                                <td style="padding:8px;font-size:11px;color:#666;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${App.escape(a.reason || "-")}</td>
                            </tr>
                        `;
                    }).join("")}
                </table>
            </div>
        `;

        return html;
    },

    renderVotes(votes, finalCategory) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        let html = `
            <div style="margin-bottom:12px;">
                ${votes.map(v => {
                    const isAgree = v.agree;
                    return `
                        <div style="display:flex;align-items:center;gap:10px;padding:10px;margin-bottom:6px;border-radius:6px;background:${isAgree ? '#f0fdf4' : '#fef2f2'};border-left:3px solid ${isAgree ? '#22c55e' : '#ef4444'};">
                            <div style="width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:${isAgree ? '#22c55e' : '#ef4444'};color:#fff;font-size:12px;font-weight:700;">
                                ${isAgree ? '✓' : '✗'}
                            </div>
                            <div style="flex:1;">
                                <div style="font-weight:600;font-size:13px;">${App.escape(v.agent_name)}</div>
                                <div style="font-size:11px;color:#666;">${App.escape(v.reason || (isAgree ? t("classify.agree") : t("classify.disagree")))}</div>
                            </div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;

        const agreeCount = votes.filter(v => v.agree).length;
        html += `
            <div style="font-size:11px;color:#888;padding:8px;background:#f9f9f9;border-radius:4px;">
                ${t("classify.vote_result")}: ${agreeCount}/${votes.length} ${t("classify.agree")}
            </div>
        `;

        return html;
    },

    renderPaxos(logs) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        if (!logs.length) return App.empty(t("classify.no_paxos_logs"));

        const propose = logs.find(l => l.phase === "propose");
        const votes = logs.filter(l => l.phase === "vote");
        const consensus = logs.find(l => l.phase === "consensus");
        const isAccepted = consensus && consensus.result === "accepted";
        let delay = 0;
        const step = (d) => { delay += d; return delay; };

        let html = '<div class="paxos-anim">';

        // 1. Proposer 提议
        if (propose) {
            const name = (propose.agent || "?").substring(0, 2).toUpperCase();
            html += `
                <div class="paxos-proposer-line" style="animation-delay:${step(0)}s">
                    <div class="agent-dot">${App.escape(name)}</div>
                    <div>
                        <div class="proposal-text">${t("classify.phase_propose") || "提议"}: ${App.escape(propose.value || "-")}</div>
                        <div style="font-size:11px;color:#6b7280;margin-top:2px;">
                            ${App.escape(propose.agent || "")} | ${t("stats.avg_confidence")}: ${((propose.confidence || 0) * 100).toFixed(0)}%
                        </div>
                    </div>
                </div>
            `;
        }

        // 2. 投票阶段
        if (votes.length) {
            html += `<div class="paxos-arrow" style="animation-delay:${step(0.3)}s"></div>`;
            html += `
                <div class="paxos-step" style="animation-delay:${step(0.15)}s">
                    <div class="paxos-step-icon" style="background:#f5f3ff;color:#7c3aed;">🗳</div>
                    <div class="paxos-step-body">
                        <div class="paxos-step-title">${t("classify.paxos_vote") || "Acceptor 投票"}</div>
                        <div class="paxos-step-desc">${votes.length} ${t("classify.voting") || "个节点参与投票"}</div>
                        <div class="paxos-vote-row">
                            ${votes.map((v, i) => {
                                const agree = v.agree || v.result === "agree";
                                const label = (v.agent || "?").substring(0, 2).toUpperCase();
                                return `
                                    <div class="paxos-vote-chip ${agree ? 'agree' : 'reject'}" style="animation-delay:${step(0.2)}s">
                                        <span>${agree ? '✓' : '✗'}</span>
                                        <span>${App.escape(v.agent || "?")}</span>
                                    </div>
                                `;
                            }).join("")}
                        </div>
                    </div>
                </div>
            `;
        }

        // 3. 共识结果
        if (consensus) {
            html += `<div class="paxos-arrow" style="animation-delay:${step(0.3)}s"></div>`;
            const boxClass = isAccepted ? "accepted" : "fallback";
            const icon = isAccepted ? "✅" : "📊";
            const label = isAccepted
                ? (t("classify.consensus_reached") || "共识达成")
                : (t("classify.fallback_vote") || "多数投票");
            const agreeCount = votes.filter(v => v.agree || v.result === "agree").length;
            html += `
                <div class="paxos-consensus-box ${boxClass}" style="animation-delay:${step(0.2)}s">
                    <span class="paxos-consensus-icon">${icon}</span>
                    <div class="paxos-consensus-label">${label}: ${App.escape(consensus.value || consensus.category || "-")}</div>
                    <div class="paxos-consensus-detail">
                        ${isAccepted ? `${agreeCount}/${votes.length} ${t("classify.agree") || "同意"}` : consensus.result || ""}
                        · ${consensus.result === "accepted" ? t("classify.paxos_consensus") : t("classify.majority_vote")}
                    </div>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }
};
