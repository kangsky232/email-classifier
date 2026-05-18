const ClusterPage = {
    refreshInterval: null,

    _animateNumber(el, target, suffix) {
        suffix = suffix || '';
        const isFloat = String(target).includes('.');
        const decimals = isFloat ? (String(target).split('.')[1] || '').length : 0;
        const duration = 600;
        const start = performance.now();
        const from = 0;
        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = from + (target - from) * ease;
            el.textContent = (decimals > 0 ? current.toFixed(decimals) : Math.round(current)) + suffix;
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    },

    _animateAllNumbers(container) {
        const els = container.querySelectorAll('[data-target]');
        els.forEach(el => {
            const target = parseFloat(el.dataset.target);
            const suffix = el.dataset.suffix || '';
            if (!isNaN(target)) this._animateNumber(el, target, suffix);
        });
    },

    async render() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const page = document.getElementById('page-cluster');
        page.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>${t("cluster.title")}</h2>
                    <p class="page-subtitle">${t("cluster.subtitle")}</p>
                </div>
                <div style="display:flex;gap:8px;">
                    <button class="btn" type="button" onclick="ClusterPage.refresh()">${t("common.refresh")}</button>
                    <button id="auto-refresh-btn" class="btn btn-primary" type="button" onclick="ClusterPage.toggleAutoRefresh()">${t("monitor.refresh")}</button>
                </div>
            </div>

            <div id="cluster-overview" class="stats-grid" style="margin-bottom:16px;"></div>

            <div class="grid two" style="margin-bottom:16px;">
                <div class="card">
                    <h3 class="card-title">${t("cluster.nodes")}</h3>
                    <div id="cluster-nodes"></div>
                </div>
                <div class="card">
                    <h3 class="card-title">${t("cluster.hashring")}</h3>
                    <div id="hashring-info"></div>
                </div>
            </div>

            <div class="grid two" style="margin-bottom:16px;">
                <div class="card">
                    <h3 class="card-title">${t("cluster.resources")}</h3>
                    <div id="resource-metrics"></div>
                </div>
                <div class="card">
                    <h3 class="card-title">${t("cluster.paxos_stats")}</h3>
                    <div id="paxos-stats"></div>
                </div>
            </div>

            <div class="card" style="margin-bottom:16px;">
                <h3 class="card-title">${t("cluster.lb")}</h3>
                <div id="load-balance"></div>
            </div>

            <div class="card" style="margin-bottom:16px;">
                <h3 class="card-title">${t("cluster.gfs")}</h3>
                <div id="gfs-overview"></div>
            </div>

            <div class="card" style="margin-bottom:16px;">
                <h3 class="card-title">${t("cluster.smart_lb")}</h3>
                <div id="lb-stats"></div>
            </div>

            <div class="grid two" style="margin-bottom:16px;">
                <div class="card">
                    <h3 class="card-title">${t("cluster.registry")}</h3>
                    <div id="service-registry"></div>
                </div>
                <div class="card">
                    <h3 class="card-title">${t("cluster.health_probes")}</h3>
                    <div id="health-probes"></div>
                </div>
            </div>
            <div class="grid two">
                <div class="card">
                    <h3 class="card-title">${t("cluster.circuit_breaker")}</h3>
                    <div id="circuit-breakers"></div>
                </div>
                <div class="card">
                    <h3 class="card-title">${t("cluster.tracing")}</h3>
                    <div id="tracing-stats"></div>
                </div>
            </div>
        `;

        await this.refresh();
    },

    async refresh() {
        try {
            const [status, metrics, gfs, lb, services, health, breakers, traces] = await Promise.all([
                API.get('/api/cluster/status'),
                API.get('/api/cluster/metrics'),
                API.get('/api/gfs/cluster'),
                API.get('/api/lb/stats'),
                API.get('/api/cloud/services'),
                API.get('/api/cloud/health'),
                API.get('/api/cloud/circuit-breakers'),
                API.get('/api/cloud/traces')
            ]);

            this.renderOverview(status, metrics);
            this.renderNodes(status.nodes || []);
            this.renderHashRing(status.ring || {});
            this.renderResources(metrics.local || {});
            this.renderPaxos(metrics.cluster || {});
            this.renderLoadBalance(status.nodes || []);
            this.renderGFS(gfs);
            this.renderLB(lb);
            this.renderServices(services);
            this.renderHealth(health);
            this.renderCircuitBreakers(breakers);
            this.renderTracing(traces);
        } catch (e) {
            console.error('Failed to fetch cluster data:', e);
            const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
            App.showToast(t("cluster.load_failed") + ': ' + e.message, 'error');
        }
    },

    renderOverview(status, metrics) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('cluster-overview');
        const cluster = metrics.cluster || {};

        box.innerHTML = `
            <div class="stat-card">
                <div class="stat-label">${t("cluster.total_nodes")}</div>
                <div class="stat-value" data-target="${status.total_nodes || 0}">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">${t("cluster.healthy_nodes")}</div>
                <div class="stat-value" style="color:#52c41a;" data-target="${status.healthy_count || 0}">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">${t("cluster.fault_nodes")}</div>
                <div class="stat-value" style="color:${(status.failed_count || 0) > 0 ? '#ff4d4f' : '#52c41a'};" data-target="${status.failed_count || 0}">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">${t("queue.total_messages")}</div>
                <div class="stat-value" data-target="${cluster.total_requests || 0}">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">${t("stats.avg_confidence")}</div>
                <div class="stat-value" data-target="${cluster.avg_response_time || 0}" data-suffix="ms">0ms</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">${t("cluster.paxos_stats")}</div>
                <div class="stat-value" style="color:#52c41a;" data-target="${cluster.paxos_success_rate || 100}" data-suffix="%">0%</div>
            </div>
        `;
        this._animateAllNumbers(box);
    },

    renderNodes(nodes) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('cluster-nodes');
        if (!nodes.length) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const statusColors = {
            'online': { bg: '#e6f7ff', color: '#1890ff', text: t("cluster.online") },
            'offline': { bg: '#fff1f0', color: '#ff4d4f', text: t("cluster.offline") },
            'failed': { bg: '#fff1f0', color: '#ff4d4f', text: t("cluster.fault") }
        };

        box.innerHTML = nodes.map(node => {
            const status = node.failed ? 'failed' : (node.status || 'online');
            const st = statusColors[status] || statusColors['offline'];
            const load = node.load || 0;
            const loadColor = load > 100 ? '#ff4d4f' : load > 50 ? '#faad14' : '#52c41a';

            return `
                <div style="padding:10px 12px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>${App.escape(node.name || node.id)}</strong>
                        <span style="background:${st.bg};color:${st.color};padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">${st.text}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                        <div style="text-align:right;">
                            <div style="font-size:11px;color:#999;">${t("cluster.lb")}</div>
                            <div style="font-size:14px;font-weight:600;color:${loadColor};">${load}</div>
                        </div>
                        ${node.url ? `<span style="font-size:11px;color:#999;">${App.escape(node.url)}</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    },

    renderHashRing(ring) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('hashring-info');
        const total = ring.total_nodes || 0;
        const failed = ring.failed_nodes || 0;
        const virtual = ring.virtual_nodes || 0;

        // 可视化哈希环
        const size = 200;
        const center = size / 2;
        const radius = 80;

        let svg = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="margin:0 auto;display:block;">`;

        // 外圈
        svg += `<circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="#e8e8e8" stroke-width="2"/>`;

        // 节点分布
        const nodes = Array.from({ length: Math.min(virtual, 20) }, (_, i) => {
            const angle = (i / Math.min(virtual, 20)) * 360;
            const rad = (angle * Math.PI) / 180;
            const x = center + radius * Math.cos(rad);
            const y = center + radius * Math.sin(rad);
            const color = i < (virtual - failed) ? '#1890ff' : '#ff4d4f';
            return { x, y, color };
        });

        nodes.forEach(n => {
            svg += `<circle cx="${n.x}" cy="${n.y}" r="4" fill="${n.color}"/>`;
        });

        // 中心文字
        svg += `<text x="${center}" y="${center - 8}" text-anchor="middle" font-size="14" font-weight="bold" fill="#333">${total}</text>`;
        svg += `<text x="${center}" y="${center + 10}" text-anchor="middle" font-size="10" fill="#999">${t("cluster.nodes")}</text>`;

        svg += '</svg>';

        box.innerHTML = `
            <div style="text-align:center;padding:12px;">
                ${svg}
                <div style="margin-top:12px;">
                    <div style="display:flex;justify-content:center;gap:20px;font-size:12px;">
                        <div>
                            <span style="display:inline-block;width:10px;height:10px;background:#1890ff;border-radius:50%;margin-right:4px;"></span>
                            ${t("cluster.healthy")}
                        </div>
                        <div>
                            <span style="display:inline-block;width:10px;height:10px;background:#ff4d4f;border-radius:50%;margin-right:4px;"></span>
                            ${t("cluster.fault")}
                        </div>
                    </div>
                </div>
                <div style="margin-top:12px;padding:8px;background:#f9f9f9;border-radius:4px;font-size:12px;color:#666;">
                    ${t("cluster.hashring")}: ${virtual} | ${t("cluster.total_nodes")}: ${total} | ${t("cluster.fault_nodes")}: ${failed}
                </div>
            </div>
        `;
    },

    renderResources(local) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('resource-metrics');
        if (!local.cpu_percent && local.cpu_percent !== 0) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const cpuColor = local.cpu_percent > 80 ? '#ff4d4f' : local.cpu_percent > 50 ? '#faad14' : '#52c41a';
        const memColor = local.memory_percent > 80 ? '#ff4d4f' : local.memory_percent > 50 ? '#faad14' : '#52c41a';
        const diskColor = local.disk_percent > 80 ? '#ff4d4f' : local.disk_percent > 50 ? '#faad14' : '#52c41a';

        box.innerHTML = `
            <div style="padding:12px;">
                <div style="margin-bottom:16px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:12px;">
                        <span>CPU</span>
                        <span style="font-weight:600;color:${cpuColor};">${local.cpu_percent}%</span>
                    </div>
                    <div style="height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">
                        <div style="width:${local.cpu_percent}%;height:100%;background:${cpuColor};border-radius:4px;transition:width 0.3s;"></div>
                    </div>
                </div>

                <div style="margin-bottom:16px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:12px;">
                        <span>Memory</span>
                        <span style="font-weight:600;color:${memColor};">${local.memory_percent}% (${local.memory_used_mb}MB / ${local.memory_total_mb}MB)</span>
                    </div>
                    <div style="height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">
                        <div style="width:${local.memory_percent}%;height:100%;background:${memColor};border-radius:4px;transition:width 0.3s;"></div>
                    </div>
                </div>

                <div style="margin-bottom:16px;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:12px;">
                        <span>Disk</span>
                        <span style="font-weight:600;color:${diskColor};">${local.disk_percent}% (${local.disk_used_gb}GB / ${local.disk_total_gb}GB)</span>
                    </div>
                    <div style="height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">
                        <div style="width:${local.disk_percent}%;height:100%;background:${diskColor};border-radius:4px;transition:width 0.3s;"></div>
                    </div>
                </div>

                <div style="display:flex;gap:12px;font-size:12px;color:#666;">
                    <div>Processes: ${local.process_count || 0}</div>
                    <div>Net TX: ${this.formatBytes(local.network_bytes_sent)}</div>
                    <div>Net RX: ${this.formatBytes(local.network_bytes_recv)}</div>
                </div>
            </div>
        `;
    },

    renderPaxos(cluster) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('paxos-stats');
        const total = cluster.paxos_consensus_count || 0;
        const success = cluster.paxos_success_count || 0;
        const rate = cluster.paxos_success_rate || 100;
        const rateColor = rate >= 95 ? '#52c41a' : rate >= 80 ? '#faad14' : '#ff4d4f';

        box.innerHTML = `
            <div style="padding:12px;">
                <div style="text-align:center;margin-bottom:16px;">
                    <div style="font-size:36px;font-weight:700;color:${rateColor};" data-target="${rate}" data-suffix="%">0%</div>
                    <div style="font-size:12px;color:#999;">${t("cluster.paxos_stats")}</div>
                </div>

                <div style="display:flex;gap:12px;margin-bottom:16px;">
                    <div style="flex:1;text-align:center;padding:12px;background:#f0fdf4;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#16a34a;" data-target="${success}">0</div>
                        <div style="font-size:11px;color:#666;">${t("cluster.healthy")}</div>
                    </div>
                    <div style="flex:1;text-align:center;padding:12px;background:#fff7ed;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#d97706;" data-target="${total - success}">0</div>
                        <div style="font-size:11px;color:#666;">${t("cluster.fault")}</div>
                    </div>
                    <div style="flex:1;text-align:center;padding:12px;background:#f0f7ff;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#1890ff;" data-target="${total}">0</div>
                        <div style="font-size:11px;color:#666;">${t("stats.total")}</div>
                    </div>
                </div>

                <div style="font-size:12px;color:#666;padding:8px;background:#f9f9f9;border-radius:4px;">
                    ${t("stats.avg_confidence")}: ${cluster.avg_response_time || 0}ms
                </div>
            </div>
        `;
        this._animateAllNumbers(box);
    },

    renderLoadBalance(nodes) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('load-balance');
        if (!nodes.length) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const maxLoad = Math.max(...nodes.map(n => n.load || 0), 1);

        box.innerHTML = `
            <div style="padding:12px;">
                <div style="margin-bottom:12px;font-size:12px;color:#666;">
                    ${t("cluster.lb")}: ${t("cluster.hashring")}
                </div>
                <div style="display:flex;gap:8px;align-items:end;height:120px;padding:8px 0;">
                    ${nodes.map(node => {
                        const load = node.load || 0;
                        const height = Math.max((load / maxLoad) * 100, 10);
                        const color = node.failed ? '#ff4d4f' : '#1890ff';
                        return `
                            <div style="flex:1;display:flex;flex-direction:column;align-items:center;">
                                <div style="font-size:11px;font-weight:600;color:${color};margin-bottom:4px;">${load}</div>
                                <div style="width:100%;height:${height}px;background:${color};border-radius:4px 4px 0 0;transition:height 0.3s;"></div>
                                <div style="font-size:10px;color:#999;margin-top:4px;white-space:nowrap;">${App.escape(node.name || node.id)}</div>
                            </div>
                        `;
                    }).join('')}
                </div>
                <div style="margin-top:12px;padding:8px;background:#f9f9f9;border-radius:4px;font-size:11px;color:#666;">
                    ${t("cluster.lb")}
                </div>
            </div>
        `;
    },

    formatBytes(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let i = 0;
        let value = bytes;
        while (value >= 1024 && i < units.length - 1) {
            value /= 1024;
            i++;
        }
        return `${value.toFixed(1)} ${units[i]}`;
    },

    renderGFS(gfs) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('gfs-overview');
        if (!gfs) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const totalSize = this.formatBytes(gfs.total_size || 0);

        box.innerHTML = `
            <div style="padding:12px;">
                <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px;">
                    <div style="text-align:center;padding:12px;background:#f0f7ff;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#1890ff;">${gfs.total_files || 0}</div>
                        <div style="font-size:11px;color:#666;">Files</div>
                    </div>
                    <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#16a34a;">${gfs.total_chunks || 0}</div>
                        <div style="font-size:11px;color:#666;">Chunks</div>
                    </div>
                    <div style="text-align:center;padding:12px;background:#fff7ed;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#d97706;">${gfs.total_servers || 0}</div>
                        <div style="font-size:11px;color:#666;">ChunkServer</div>
                    </div>
                    <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#52c41a;">${gfs.online_servers || 0}</div>
                        <div style="font-size:11px;color:#666;">${t("cluster.online")}</div>
                    </div>
                    <div style="text-align:center;padding:12px;background:#f9f0ff;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#722ed1;">${totalSize}</div>
                        <div style="font-size:11px;color:#666;">${t("stats.total")}</div>
                    </div>
                </div>

                <div style="display:flex;gap:16px;font-size:12px;color:#666;padding:8px;background:#f9f9f9;border-radius:4px;">
                    <div>Replication: ${gfs.replication_factor || 3}</div>
                    <div>|</div>
                    <div>Chunk: 4MB</div>
                    <div>|</div>
                    <div>3x Replicas</div>
                </div>

                <div style="margin-top:12px;">
                    <button class="btn" onclick="ClusterPage.rebalanceGFS()" style="font-size:12px;">${t("cluster.gfs")}</button>
                </div>
            </div>
        `;
    },

    renderLB(lb) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('lb-stats');
        if (!lb || !lb.nodes) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const nodes = Object.entries(lb.nodes);
        const totalRequests = lb.total_requests || 0;

        box.innerHTML = `
            <div style="padding:12px;">
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;">
                    <div style="text-align:center;padding:12px;background:#f0f7ff;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#1890ff;" data-target="${lb.total_nodes || 0}">0</div>
                        <div style="font-size:11px;color:#666;">${t("cluster.total_nodes")}</div>
                    </div>
                    <div style="text-align:center;padding:12px;background:#f0fdf4;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#16a34a;" data-target="${lb.online_nodes || 0}">0</div>
                        <div style="font-size:11px;color:#666;">${t("cluster.healthy_nodes")}</div>
                    </div>
                    <div style="text-align:center;padding:12px;background:#fff7ed;border-radius:6px;">
                        <div style="font-size:20px;font-weight:700;color:#d97706;" data-target="${totalRequests}">0</div>
                        <div style="font-size:11px;color:#666;">${t("queue.total_messages")}</div>
                    </div>
                </div>

                <div style="margin-bottom:12px;font-size:12px;color:#666;">${t("cluster.nodes")}:</div>
                ${nodes.map(([id, data]) => {
                    const info = data.info || {};
                    const stats = data.stats || {};
                    const status = info.status === 'online' ? t("cluster.online") : t("cluster.offline");
                    const statusColor = info.status === 'online' ? '#52c41a' : '#ff4d4f';
                    const avgTime = stats.avg_response_time ? stats.avg_response_time.toFixed(1) : '0';
                    const successRate = stats.requests > 0 ? ((stats.successes / stats.requests) * 100).toFixed(1) : '100';

                    return `
                        <div style="padding:8px 12px;border:1px solid #f0f0f0;border-radius:4px;margin-bottom:8px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div>
                                    <strong>${App.escape(id)}</strong>
                                    <span style="color:${statusColor};font-size:11px;margin-left:8px;">${status}</span>
                                </div>
                                <div style="display:flex;gap:16px;font-size:11px;color:#666;">
                                    <div>W: ${info.weight || 1}</div>
                                    <div>Req: ${stats.requests || 0}</div>
                                    <div>OK: ${successRate}%</div>
                                    <div>Avg: ${avgTime}ms</div>
                                    <div>Conn: ${stats.active_connections || 0}</div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('')}

                <div style="margin-top:12px;padding:8px;background:#f9f9f9;border-radius:4px;font-size:11px;color:#666;">
                    ${t("cluster.smart_lb")}
                </div>
            </div>
        `;
        this._animateAllNumbers(box);
    },

    async rebalanceGFS() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        try {
            await API.post('/api/gfs/rebalance');
            App.showToast(t("common.success"), 'success');
            this.refresh();
        } catch (e) {
            App.showToast(t("common.error") + ': ' + e.message, 'error');
        }
    },

    renderServices(services) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('service-registry');
        if (!services || Object.keys(services).length === 0) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        let html = '<div style="padding:12px;">';
        for (const [name, instances] of Object.entries(services)) {
            html += `<div style="margin-bottom:12px;">
                <div style="font-weight:600;font-size:13px;margin-bottom:6px;">${App.escape(name)}</div>`;
            for (const inst of instances) {
                const statusColor = inst.status === 'UP' ? '#52c41a' : '#ff4d4f';
                html += `
                    <div style="padding:6px 8px;background:#f9f9f9;border-radius:4px;margin-bottom:4px;display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span style="display:inline-block;width:8px;height:8px;background:${statusColor};border-radius:50%;margin-right:6px;"></span>
                            <span style="font-size:12px;">${App.escape(inst.service_id)}</span>
                        </div>
                        <span style="font-size:11px;color:#666;">${App.escape(inst.url)}</span>
                    </div>`;
            }
            html += '</div>';
        }
        html += '</div>';
        box.innerHTML = html;
    },

    renderHealth(health) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('health-probes');
        if (!health || !health.checks) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const statusColor = health.status === 'UP' ? '#52c41a' : '#ff4d4f';
        let html = `
            <div style="padding:12px;">
                <div style="text-align:center;margin-bottom:12px;">
                    <div style="font-size:24px;font-weight:700;color:${statusColor};">${health.status}</div>
                    <div style="font-size:11px;color:#999;">${t("cluster.health_probes")}</div>
                </div>
                <div style="font-size:11px;color:#666;margin-bottom:8px;">Uptime: ${Math.floor(health.uptime_seconds / 60)} min</div>
        `;

        for (const [name, check] of Object.entries(health.checks)) {
            const checkColor = check.status === 'UP' ? '#52c41a' : '#ff4d4f';
            html += `
                <div style="padding:6px 8px;background:#f9f9f9;border-radius:4px;margin-bottom:4px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span style="display:inline-block;width:8px;height:8px;background:${checkColor};border-radius:50%;margin-right:6px;"></span>
                            <span style="font-size:12px;">${App.escape(name)}</span>
                        </div>
                        <span style="font-size:10px;padding:2px 6px;background:${checkColor}20;color:${checkColor};border-radius:3px;">${check.probe_type}</span>
                    </div>
                    ${check.last_error ? `<div style="font-size:10px;color:#ff4d4f;margin-top:4px;">${App.escape(check.last_error)}</div>` : ''}
                </div>`;
        }
        html += '</div>';
        box.innerHTML = html;
    },

    renderCircuitBreakers(breakers) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('circuit-breakers');
        if (!breakers || Object.keys(breakers).length === 0) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const stateLabels = { closed: t("cluster.healthy"), open: t("cluster.fault"), half_open: t("cluster.unhealthy") };
        const stateIcons = { closed: '&#10003;', open: '&#10007;', half_open: '&#9675;' };

        let html = '<div style="padding:12px;">';
        for (const [name, stats] of Object.entries(breakers)) {
            const label = stateLabels[stats.state] || stats.state;
            const icon = stateIcons[stats.state] || '?';
            const stateClass = stats.state === 'half_open' ? 'half_open' : stats.state;

            html += `
                <div style="padding:10px;border:1px solid #f0f0f0;border-radius:6px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <div style="display:flex;align-items:center;gap:10px;">
                            <div class="cb-ring ${stateClass}">${icon}</div>
                            <strong style="font-size:13px;">${App.escape(name)}</strong>
                        </div>
                        <span style="font-size:11px;color:#999;">${label}</span>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:11px;">
                        <div style="text-align:center;padding:6px;background:#f9f9f9;border-radius:4px;">
                            <div style="font-weight:600;">${stats.total_calls}</div>
                            <div style="color:#999;">Total</div>
                        </div>
                        <div style="text-align:center;padding:6px;background:#f9f9f9;border-radius:4px;">
                            <div style="font-weight:600;color:#ff4d4f;">${stats.failure_count}</div>
                            <div style="color:#999;">${t("cluster.fault")}</div>
                        </div>
                        <div style="text-align:center;padding:6px;background:#f9f9f9;border-radius:4px;">
                            <div style="font-weight:600;">${(stats.failure_rate * 100).toFixed(1)}%</div>
                            <div style="color:#999;">Rate</div>
                        </div>
                    </div>
                </div>`;
        }
        html += '</div>';
        box.innerHTML = html;
    },

    renderTracing(traces) {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const box = document.getElementById('tracing-stats');
        if (!traces) {
            box.innerHTML = `<p style="padding:12px;color:#999;">${t("common.no_data")}</p>`;
            return;
        }

        const stats = traces.stats || {};
        const recentTraces = traces.traces || [];

        let html = `
            <div style="padding:12px;">
                <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:12px;">
                    <div style="text-align:center;padding:10px;background:#f0f7ff;border-radius:6px;">
                        <div style="font-size:18px;font-weight:700;color:#1890ff;" data-target="${stats.total_traces || 0}">0</div>
                        <div style="font-size:10px;color:#666;">Traces</div>
                    </div>
                    <div style="text-align:center;padding:10px;background:#f0fdf4;border-radius:6px;">
                        <div style="font-size:18px;font-weight:700;color:#16a34a;" data-target="${stats.total_spans || 0}">0</div>
                        <div style="font-size:10px;color:#666;">Spans</div>
                    </div>
                </div>
                ${stats.avg_duration_ms ? `<div style="font-size:11px;color:#666;margin-bottom:8px;">Avg: ${stats.avg_duration_ms.toFixed(1)}ms</div>` : ''}
        `;

        if (recentTraces.length > 0) {
            html += `<div style="font-size:11px;color:#999;margin-bottom:6px;">${t("cluster.tracing")}:</div>`;
            for (const trace of recentTraces.slice(0, 5)) {
                const statusColor = trace.status === 'OK' ? '#52c41a' : '#ff4d4f';
                html += `
                    <div style="padding:6px 8px;background:#f9f9f9;border-radius:4px;margin-bottom:4px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:11px;">${App.escape(trace.operation)}</span>
                            <span style="font-size:10px;color:${statusColor};">${trace.duration_ms ? trace.duration_ms.toFixed(1) + 'ms' : '-'}</span>
                        </div>
                    </div>`;
            }
        }
        html += '</div>';
        box.innerHTML = html;
        this._animateAllNumbers(box);
    },

    toggleAutoRefresh() {
        const t = (k) => typeof I18N !== 'undefined' ? I18N.t(k) : k;
        const btn = document.getElementById('auto-refresh-btn');
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            btn.textContent = t("monitor.refresh");
            btn.className = 'btn btn-primary';
        } else {
            this.refreshInterval = setInterval(() => this.refresh(), 5000);
            btn.textContent = t("common.cancel");
            btn.className = 'btn btn-danger';
        }
    },

    cleanup() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
};
