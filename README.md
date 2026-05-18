# 基于 LLM Agent + Paxos 共识的分布式邮件分类系统 (v2)

分布式架构版本。4 个独立 LLM Agent 节点通过 Paxos 共识协议达成邮件分类决策。

## 架构总览

```
浏览器 ─── Flask Gateway (port 5000) ─── WebSocket (SocketIO)
                    │
        ┌───────────┼───────────────────┐
        ▼           ▼                   ▼
   Agent-1      Agent-2  ... Agent-4   MySQL/SQLite
   (8503)       (8504)      (8506)
   LLM1/严格     LLM2/语义    LLM4/宽松
        │           │                   │
        └───── Paxos 共识 ──────────────┘
              (Prepare → Accept)
```

- **Gateway**: Flask 网关，路由、认证、WebSocket、GFS、集群管理
- **Agent 节点**: 4 个独立 Flask 进程，每个运行 LLM 分类器 + Paxos Acceptor
- **Paxos 共识**: 4 个 Acceptor 中至少 3 票达成共识（容错 1 节点故障）

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
cd v2/docker
# 配置 API Key
echo "DEEPSEEK_API_KEY=your-key-here" > ../.env
# 一键启动所有服务
docker compose up -d
```

浏览器打开 `http://localhost:5000`。

### 方式二：手动启动

```bash
cd v2
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入至少一个 LLM API Key

# 启动 4 个 Agent 节点（4 个终端）
python scripts/start_agent.py --role llm1 --port 8503 --id acceptor-1
python scripts/start_agent.py --role llm2 --port 8504 --id acceptor-2
python scripts/start_agent.py --role llm3 --port 8505 --id acceptor-3
python scripts/start_agent.py --role llm4 --port 8506 --id acceptor-4

# 启动网关
python run.py
```

### Kubernetes 部署

```bash
kubectl apply -f k8s/
# 访问 NodePort: http://<node-ip>:30500
```

## 云原生组件

| 组件 | 功能 | 接入点 |
|------|------|--------|
| **分布式链路追踪** | 每个请求自动生成 trace_id，跨 Gateway → Agent 传播 | `X-Trace-Id` Header → `tracer.start_span()` |
| **熔断器** | LLM 调用失败 3 次后熔断，60s 后半开恢复 | `circuit_breaker.get_or_create("llm-{name}")` |
| **配置中心** | LLM 配置变更自动同步，支持监听通知 | `config_center.set()/watch()` |
| **负载均衡器** | 健康感知选择节点，记录响应时间和成功率 | `load_balancer.select_node("health_aware")` |
| **服务注册中心** | Gateway + 4 Agent 自动注册，心跳保活 | `service_registry.register()/heartbeat()` |
| **健康探针** | liveness/readiness 探针，K8s 就绪 | `/api/cloud/health/live`, `/api/cloud/health/ready` |

## 文件结构

```
v2/
├── run.py                          # 网关入口
├── agent_service.py                # Agent 节点入口
├── config/
│   └── settings.py                 # 全局配置（DB、MQ、Paxos、Agent 节点列表）
│
├── gateway/
│   ├── app.py                      # Flask 应用初始化、Blueprint 注册、后台线程
│   ├── middleware.py                # 认证 (@login_required)、限流
│   └── routes/
│       ├── auth.py                 # 登录/注册/登出
│       ├── emails.py               # 邮件 CRUD
│       ├── classify.py             # 分类 API
│       ├── stats.py                # 统计 API
│       ├── cluster.py              # 集群/GFS/负载均衡/MapReduce/LLM 配置/队列/Paxos
│       └── cloud.py                # 服务注册/配置中心/链路追踪/熔断器/健康探针
│
├── services/
│   ├── classifier/
│   │   ├── base_agent.py           # Agent 抽象基类
│   │   ├── llm_agent.py            # LLM Agent（4 种差异化 Prompt、7 种 Provider）
│   │   ├── classifier.py           # 分类调度器（并行分类 → Paxos 投票 → 共识）
│   │   └── service.py              # Agent 节点 Flask 应用（/classify, /paxos/vote 等）
│   ├── consensus/
│   │   ├── acceptor.py             # Paxos Acceptor（线程安全状态机）
│   │   ├── proposer.py             # Paxos Proposer
│   │   ├── learner.py              # Paxos Learner
│   │   ├── coordinator.py          # Paxos 协调器
│   │   └── message.py              # Paxos 消息定义
│   ├── storage/
│   │   ├── master.py               # GFS Master
│   │   └── chunkserver.py          # GFS ChunkServer
│   └── mapreduce/
│       └── bayes.py                # MapReduce 朴素贝叶斯
│
├── infrastructure/
│   ├── database/
│   │   ├── db.py                   # 数据库连接池（MySQL/SQLite）
│   │   └── models.py               # 数据模型
│   ├── mq/
│   │   ├── producer.py             # MQ 生产者（线程安全重连）
│   │   ├── consumer.py             # MQ 消费者（独立 channel 线程）
│   │   ├── inprocess_queue.py      # 内存队列（deque 优化）
│   │   └── handlers.py             # 消息处理器
│   └── cluster/
│       ├── consistent_hash.py      # 一致性哈希环 + 集群管理器（无死锁）
│       ├── monitor.py              # 集群指标监控
│       └── load_balancer.py        # 负载均衡器
│
├── cloud_native/
│   ├── registry.py                 # 服务注册中心
│   ├── config_center.py            # 配置中心
│   ├── tracing.py                  # 分布式链路追踪（bounded deque）
│   ├── circuit_breaker.py          # 熔断器
│   └── health.py                   # 健康探针（liveness/readiness）
│
├── static/
│   ├── css/style.css               # 全局样式（暗色模式支持）
│   └── js/
│       ├── app.js                  # SPA 路由、页面切换、cleanup 机制
│       ├── auth.js                 # 登录/注册
│       ├── classify.js             # 分类页面
│       ├── monitor.js              # Agent 监控（WebSocket 实时更新）
│       ├── cluster.js              # 集群监控
│       ├── queue.js                # MQ 监控（WebSocket + 轮询）
│       ├── stats.js                # 数据统计
│       ├── settings.js             # LLM 配置
│       ├── paxos.js                # Paxos 演示
│       ├── email.js                # 邮件管理
│       └── i18n.js                 # 国际化
│
├── templates/index.html            # SPA 入口模板
├── tests/                          # 测试用例
├── docker/
│   ├── Dockerfile.gateway          # 网关镜像
│   ├── Dockerfile.agent            # Agent 节点镜像
│   ├── docker-compose.yml          # 一键编排（Gateway + 4 Agent + MySQL + RabbitMQ）
│   └── .dockerignore
└── k8s/
    ├── namespace.yaml              # 命名空间
    ├── configmap.yaml              # 非敏感配置
    ├── secret.yaml                 # API Key 等敏感信息
    ├── mysql-statefulset.yaml      # MySQL StatefulSet + PVC
    ├── rabbitmq-deployment.yaml    # RabbitMQ Deployment
    ├── gateway-deployment.yaml     # Gateway Deployment + NodePort
    └── agent-deployment.yaml       # 4 个 Agent Deployment + Service
```

## 核心流程

```
用户提交邮件
    │
    ▼
Gateway (POST /api/classify)
    │
    ▼
4 个 Agent 并行分类（ThreadPoolExecutor）
    │  每个 Agent 有不同分类视角：
    │  - LLM1: 严格模式（宁可误判也不放过）
    │  - LLM2: 语义分析（深层意图推断）
    │  - LLM3: 关键词驱动（实体提取）
    │  - LLM4: 宽松模式（倾向正面分类）
    │
    ▼
取置信度最高的作为 Proposer
    │
    ▼
其他 Agent 投票（POST /paxos/vote）
    │
    ▼
多数同意 → Paxos 共识达成
少数同意 → 回退到多数投票
    │
    ▼
结果写入数据库，返回前端
```

## 4 个 Agent 的差异化策略

| Agent | 角色 | 分类视角 |
|-------|------|----------|
| LLM1 | 严格模式 | 重点关注安全风险，宁可误判为可疑邮件 |
| LLM2 | 语义分析 | 从邮件深层语义和上下文推断类别 |
| LLM3 | 关键词驱动 | 通过提取关键词和实体信息判断类别 |
| LLM4 | 宽松模式 | 倾向正面分类，除非有明确负面信号 |

## LLM Provider 支持

| Provider | 环境变量 | 模型 |
|----------|----------|------|
| Ollama (本地) | 自动检测 | gpt-oss:120b-cloud |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| 通义千问 | `DASHSCOPE_API_KEY` | qwen-turbo |
| ChatGPT | `OPENAI_API_KEY` | gpt-3.5-turbo |
| 文心一言 | `ERNIE_API_KEY` + `ERNIE_SECRET_KEY` | ERNIE-Speed-128K |
| 讯飞星火 | `SPARK_API_KEY` | generalv3.5 |
| ChatGLM | `ZHIPU_API_KEY` | glm-4-flash |
| 自定义 | `CUSTOM_LLM_URL` + `CUSTOM_LLM_KEY` | - |

配置方式：页面左侧 → 系统设置，或 `.env` 文件。

## 安全特性

- **认证**: 所有 API 端点需要登录（`@login_required`），健康探针除外
- **密码**: bcrypt + 12 轮盐值哈希
- **API Key**: 存储时加密，返回时脱敏（`sk-***abc`）
- **SECRET_KEY**: 首次生成后持久化到 `.secret_key` 文件，重启不变
- **限流**: 写操作 60 次/分钟，定期清理过期 IP
- **输入验证**: `sanitize_input()` 清洗所有用户输入
- **XSS 防护**: 前端所有内容通过 `App.escape()` 转义

## 线程安全

- `AcceptorNodeAgent`: `_lock` 保护计数器并发递增
- `Acceptor`: `_lock` 保护 Paxos 状态机（promised_id/accepted_id/accepted_value）
- `MQProducer`: `_lock` 保护重连逻辑
- `MQConsumer`: 每个消费者线程独立 connection/channel
- `ClusterManager`: 修复嵌套锁死锁（先收集 key，释放锁后再操作 hash_ring）
- `ConsistentHashRing`: `sorted_keys.remove()` 包裹 try/except

## 性能优化

- **后台健康检查**: 长生命周期 ThreadPoolExecutor，8 秒轮询，API 读缓存
- **Ollama 缓存**: 30s TTL 缓存可用性检查，避免每次 API 调用阻塞
- **内存上限**: Tracer traces/span 用 deque(maxlen=1000) 驱逐旧数据；BaseAgent.log 用 deque(maxlen=100)
- **消息日志**: InProcessMQ 和 MQConsumer 用 deque(maxlen=50) + appendleft() 替代 O(n) 的 list.insert(0)
- **限流清理**: rate_limit 字典超 1000 IP 时自动清理过期条目

## 页面说明

| 页面 | 功能 |
|------|------|
| 邮件管理 | 查看/添加邮件 |
| 分类中心 | 提交邮件，查看 4 Agent 分类 + Paxos 共识过程 |
| Agent 监控 | 节点健康状态、WebSocket 实时更新 |
| 集群监控 | 哈希环、GFS、负载均衡、MapReduce、服务注册、链路追踪、熔断器 |
| Paxos 演示 | 两阶段协议交互式演示 |
| 消息队列 | MQ 模式、队列状态、消息流 |
| 数据统计 | 分类分布、趋势图 |
| 系统设置 | LLM Provider 配置、Agent 模型选择 |

## 环境变量

参见 `.env.example`。关键变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | 自动生成并持久化 | Flask session 密钥 |
| `DB_NAME` | `mail_system` | 数据库名 |
| `PAXOS_ACCEPTOR_COUNT` | 4 | Acceptor 节点数 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DEEPSEEK_API_KEY` | (空) | DeepSeek API Key |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ 地址（不配置则用内存队列） |
