# 分布式邮件分类系统 — 团队分工文档

## 一、团队成员及角色

| 成员 | 角色 | 核心职责 |
|------|------|----------|
| 成员A | 后端算法工程师 | Paxos共识算法 + 邮件分类Agent + Flask API |
| 成员B | 前端+数据库工程师 | 前端6个页面 + 数据库设计与实现 |
| 成员C | DevOps工程师 | 消息队列 + Docker + K8s + Istio + 测试联调 |

---

## 二、详细分工

### 成员A：后端算法工程师

#### 负责文件清单

| 文件 | 说明 | 代码量 |
|------|------|--------|
| `config.py` | 全局配置管理 | 约50行 |
| `paxos/message.py` | Paxos消息定义（Prepare/Promise/Accept等） | 约100行 |
| `paxos/proposer.py` | 提议者角色实现 | 约150行 |
| `paxos/acceptor.py` | 接受者角色实现 | 约120行 |
| `paxos/learner.py` | 学习者角色实现 | 约40行 |
| `paxos/coordinator.py` | 共识协调器（核心，编排整个Paxos流程） | 约280行 |
| `agents/base_agent.py` | Agent基类（抽象接口） | 约60行 |
| `agents/rule_agent.py` | 规则引擎Agent（基于关键词匹配分类） | 约100行 |
| `agents/bayes_agent.py` | 朴素贝叶斯Agent（TF-IDF + MultinomialNB） | 约130行 |
| `agents/lr_agent.py` | 逻辑回归Agent（TF-IDF + LogisticRegression） | 约130行 |
| `agents/classifier.py` | 统一分类入口（并行调用3个Agent + Paxos共识决策） | 约180行 |
| `app.py` | Flask主应用（全部REST API路由） | 约250行 |
| **小计** | | **约1,590行** |

#### 具体任务

| 阶段 | 任务内容 | 产出 |
|------|----------|------|
| 第1天 | 编写config.py全局配置 | 配置模块 |
| 第2天 | 实现paxos/message.py消息定义 | 消息结构体 |
| 第2天 | 实现paxos/proposer.py提议者 | 提议者逻辑 |
| 第3天 | 实现paxos/acceptor.py接受者 | 接受者逻辑 |
| 第3天 | 实现paxos/learner.py学习者 + paxos/coordinator.py协调器 | 共识完整流程 |
| 第4天 | 实现agents/base_agent.py基类 | Agent接口 |
| 第4天 | 实现agents/rule_agent.py规则引擎Agent | 规则分类 |
| 第5天 | 实现agents/bayes_agent.py + agents/lr_agent.py | 两个ML Agent |
| 第5天 | 实现agents/classifier.py统一分类入口 | 分类调度器 |
| 第6天 | 实现app.py全部API接口 | 15个REST API |
| 第7天 | 联调测试 + 修bug | 稳定运行 |

#### 技术要点

- Paxos算法需理解两阶段提交（Prepare→Promise→Accept→Accepted→Learn）
- 多数派判定逻辑：收到 (N/2 + 1) 个响应即为多数派
- Agent并行分类后比较结果，一致则直接采纳，不一致则触发Paxos共识
- Flask API需处理跨域（CORS）、分页、错误处理

#### 对外接口约定

A需向B和C提供以下API：

```
POST   /api/classify              → 提交邮件分类
GET    /api/emails?page=1&limit=10 → 邮件列表
GET    /api/emails/<id>            → 邮件详情
POST   /api/emails                 → 新建邮件
PUT    /api/emails/<id>            → 更新邮件
DELETE /api/emails/<id>            → 删除邮件
GET    /api/agents/status          → Agent状态
GET    /api/paxos/logs?page=1      → Paxos日志
GET    /api/stats/overview          → 数据统计
GET    /api/config                 → 系统配置
PUT    /api/config                 → 更新配置
GET    /api/queue/status           → 消息队列状态
```

---

### 成员B：前端+数据库工程师

#### 负责文件清单

| 文件 | 说明 | 代码量 |
|------|------|--------|
| `init.sql` | 数据库建表脚本（5张表 + 初始数据） | 约80行 |
| `database/db.py` | 数据库连接封装（pymysql连接池） | 约70行 |
| `database/models.py` | 数据模型（Email/Classification/PaxosLog/FinalResult/SystemConfig的CRUD） | 约300行 |
| `templates/index.html` | HTML主页面框架（6个页面容器 + 导航栏 + 模态框） | 约80行 |
| `static/css/style.css` | 全局样式（表格、表单、卡片、图表、动画） | 约350行 |
| `static/js/app.js` | 主逻辑（路由切换、API封装、分页、Toast） | 约120行 |
| `static/js/email.js` | 邮件管理模块（列表、搜索、筛选、新建、详情、删除） | 约300行 |
| `static/js/classify.js` | 分类中心模块（输入表单、提交分类、Agent结果展示、Paxos过程展示） | 约180行 |
| `static/js/monitor.js` | Agent监控模块（Agent卡片、状态指示、队列状态） | 约80行 |
| `static/js/paxos.js` | Paxos日志模块（日志列表、分页） | 约70行 |
| `static/js/stats.js` | 数据统计模块（统计卡片、饼图、柱状图） | 约140行 |
| `static/js/settings.js` | 系统设置模块（类别管理、Paxos参数、Agent配置） | 约160行 |
| **小计** | | **约1,830行** |

#### 具体任务

| 阶段 | 任务内容 | 产出 |
|------|----------|------|
| 第1天 | 设计数据库表结构，编写init.sql | 5张数据表 |
| 第1天 | 实现database/db.py数据库连接 | 连接模块 |
| 第1天 | 实现database/models.py全部数据模型 | ORM层 |
| 第2天 | 编写index.html主页面框架 | 页面骨架 |
| 第2天 | 编写style.css全局样式 | 样式文件 |
| 第3天 | 实现app.js主逻辑 + email.js邮件管理 | 邮件页面 |
| 第4天 | 实现classify.js分类中心 | 核心交互页面 |
| 第4天 | 实现paxos.js Paxos日志页面 | 日志页面 |
| 第5天 | 实现monitor.js Agent监控 + stats.js数据统计 | 监控和统计页面 |
| 第5天 | 实现settings.js系统设置 | 设置页面 |
| 第6天 | 前端整体优化（动画、响应式、错误处理） | 用户体验优化 |
| 第7天 | 前后端联调 + UI修复 | 完整页面 |

#### 技术要点

- 数据库设计需考虑外键关联（emails → classifications → paxos_logs → final_results）
- 前端用原生JavaScript，不依赖框架，通过fetch API调用后端
- 分页组件可复用（renderPagination函数在app.js中定义）
- 饼图用CSS conic-gradient实现，柱状图用flex布局+动态高度
- 模态框用于展示邮件详情和新建邮件

#### 与A的协作

- 第1天与A对齐API接口格式（请求参数、响应结构）
- 在A的API未完成前，先用mock数据开发前端
- A完成后替换真实接口，进行联调

#### 与C的协作

- 数据库初始化脚本init.sql需与C的Docker/K8s配置中的ConfigMap保持一致
- 前端静态资源路径需与Flask的static_folder和template_folder配置一致

---

### 成员C：DevOps工程师

#### 负责文件清单

| 文件 | 说明 | 代码量 |
|------|------|--------|
| `requirements.txt` | Python依赖清单 | 约10行 |
| `.env` | 环境变量配置 | 约12行 |
| `mq/producer.py` | RabbitMQ消息生产者（连接、声明队列、发送消息） | 约120行 |
| `mq/consumer.py` | RabbitMQ消息消费者（连接、消费、队列状态查询） | 约150行 |
| `docker/Dockerfile.app` | Flask应用Docker镜像 | 约12行 |
| `docker/Dockerfile.agent` | Agent服务Docker镜像 | 约12行 |
| `docker/docker-compose.yml` | 本地编排（MySQL + RabbitMQ + App + Agent） | 约70行 |
| `k8s/namespace.yaml` | K8s命名空间 | 约8行 |
| `k8s/mysql.yaml` | MySQL StatefulSet + Service + Secret + ConfigMap | 约150行 |
| `k8s/app.yaml` | Flask Deployment(3副本) + Service + Ingress | 约90行 |
| `k8s/agent.yaml` | Agent Deployment | 约50行 |
| `k8s/rabbitmq.yaml` | RabbitMQ Deployment + Service | 约50行 |
| `k8s/istio.yaml` | Istio Gateway + VirtualService + DestinationRule + PeerAuthentication | 约120行 |
| **小计** | | **约704行** |

#### 具体任务

| 阶段 | 任务内容 | 产出 |
|------|----------|------|
| 第1天 | 编写requirements.txt和.env | 依赖和环境配置 |
| 第1天 | 实现mq/producer.py消息生产者 | 消息发送模块 |
| 第2天 | 实现mq/consumer.py消息消费者 | 消息消费模块 |
| 第2天 | 测试RabbitMQ消息收发 | 队列通信验证 |
| 第3天 | 编写Dockerfile.app和Dockerfile.agent | Docker镜像 |
| 第3天 | 编写docker-compose.yml | 本地编排 |
| 第3天 | 本地Docker构建测试 | 镜像验证 |
| 第4天 | 编写k8s/namespace.yaml + k8s/mysql.yaml | K8s MySQL部署 |
| 第4天 | 编写k8s/app.yaml + k8s/agent.yaml + k8s/rabbitmq.yaml | K8s应用部署 |
| 第5天 | 编写k8s/istio.yaml | Istio服务网格 |
| 第5天 | 协助A或B（哪个进度慢帮哪个） | 团队协作 |
| 第6天 | 全链路测试（本地→Docker→K8s） | 端到端验证 |
| 第7天 | 部署演示环境 + 答辩准备 | 演示就绪 |

#### 技术要点

- RabbitMQ需声明4个队列：email_input、classification_result、paxos_proposal、final_action
- Docker Compose中MySQL需设置healthcheck，App需depends_on等待MySQL就绪
- K8s中MySQL用StatefulSet（有状态）+ PVC持久化存储
- K8s中App用Deployment（3副本）+ Service（ClusterIP）+ Ingress（外部访问）
- Istio配置包含Gateway（入口）、VirtualService（路由）、DestinationRule（负载均衡）、PeerAuthentication（mTLS）

#### 与A的协作

- 消息队列的队列名和消息格式需与A的app.py中的调用一致
- 环境变量名（DB_HOST、RABBITMQ_HOST等）需与A的config.py一致

#### 与B的协作

- init.sql内容需与B设计的数据库表结构一致
- Docker中的端口映射需与前端访问地址一致

---

## 三、协作时间线

```
第1天 ──────────────────────────────────────────────────────────
  A: config.py全局配置
  B: 数据库设计 + init.sql + db.py + models.py
  C: requirements.txt + .env + mq/producer.py
  📋 会议: 对齐API接口格式、数据库表结构、消息队列格式

第2天 ──────────────────────────────────────────────────────────
  A: Paxos消息定义 + Proposer提议者
  B: HTML主页面框架 + CSS样式
  C: mq/consumer.py + 测试RabbitMQ
  📋 A+B: 前端开始用mock数据开发

第3天 ──────────────────────────────────────────────────────────
  A: Acceptor + Learner + Coordinator（Paxos完整流程）
  B: 邮件管理页面（email.js）+ 主逻辑（app.js）
  C: Dockerfile + docker-compose.yml
  ✅ 检查点: Paxos算法可单机运行测试

第4天 ──────────────────────────────────────────────────────────
  A: Agent基类 + 规则引擎Agent + 朴素贝叶斯Agent
  B: 分类中心页面（classify.js）+ Paxos日志页面（paxos.js）
  C: K8s配置（namespace + mysql + app + agent + rabbitmq）
  ✅ 检查点: Agent分类可独立测试

第5天 ──────────────────────────────────────────────────────────
  A: 逻辑回归Agent + classifier.py统一入口
  B: Agent监控（monitor.js）+ 数据统计（stats.js）+ 设置（settings.js）
  C: Istio配置 + 协助A或B
  ✅ 检查点: 分类全流程可跑通（Agent分类 → Paxos共识 → 结果展示）

第6天 ──────────────────────────────────────────────────────────
  A: Flask API全部完成
  B: 前端优化（动画、响应式、错误处理）
  C: 全链路测试
  📋 全员联调: 前端 ↔ 后端 ↔ 数据库 ↔ 消息队列

第7天 ──────────────────────────────────────────────────────────
  全员: 修复联调发现的问题
  全员: 部署Docker演示环境
  全员: 答辩PPT准备 + 演示排练
```

---

## 四、联调节点

| 时间 | 联调内容 | 参与人 | 验收标准 |
|------|----------|--------|----------|
| 第4天 | 前端页面 ↔ 后端API（mock数据） | A + B | 页面能正常显示mock数据 |
| 第5天 | Agent分类 → Paxos共识 → 数据库写入 | A | 输入邮件能返回分类结果 |
| 第6天 | 前端 ↔ 后端 ↔ 数据库 ↔ 消息队列 | 全员 | 端到端流程跑通 |
| 第7天 | Docker环境全流程演示 | 全员 | 容器化部署成功 |

---

## 五、接口约定（第1天必须确认）

### API响应格式

```json
// 成功响应
{
    "success": true,
    "data": { ... }
}

// 列表响应
{
    "total": 100,
    "data": [...],
    "page": 1,
    "limit": 10
}

// 错误响应
{
    "error": "错误信息"
}
```

### 分类API请求/响应

```json
// POST /api/classify 请求
{
    "sender": "boss@company.com",
    "subject": "关于开会的通知",
    "content": "请各位明天下午3点开会"
}

// POST /api/classify 响应
{
    "success": true,
    "email_id": 1,
    "final_category": "会议通知",
    "method": "agent_consensus",
    "agents": [
        {"agent_name": "Agent A", "method": "rule_engine", "category": "会议通知", "confidence": 0.85},
        {"agent_name": "Agent B", "method": "naive_bayes", "category": "会议通知", "confidence": 0.92},
        {"agent_name": "Agent C", "method": "logistic_regression", "category": "会议通知", "confidence": 0.88}
    ],
    "paxos_log": [],
    "message": "Agent结果一致 (3/3)，直接采纳"
}
```

### 消息队列格式

```json
// email_input 队列
{"type": "new_email", "data": {"email_id": 1, "sender": "...", "subject": "...", "content": "..."}}

// classification_result 队列
{"type": "classification_result", "data": {"email_id": 1, "result": {...}}}

// paxos_proposal 队列
{"type": "paxos_proposal", "data": {"email_id": 1, "proposal_id": 1, "value": "..."}}
```

---

## 六、风险应对

| 风险 | 概率 | 应对方案 |
|------|------|----------|
| A的Paxos算法实现超时 | 中 | C协助A，或简化为单轮Paxos |
| B的前端工作量大 | 中 | A写完API后帮B处理页面逻辑 |
| MySQL连接失败 | 低 | 本地开发可用SQLite替代，第6天换回MySQL |
| RabbitMQ连接失败 | 低 | 消息队列为可选模块，不影响核心功能 |
| 联调发现大量bug | 中 | 第6天全天留给联调，不留到第7天 |
| K8s/Istio环境搭建困难 | 中 | 用Docker Compose演示即可，K8s配置作为文档展示 |

---

## 七、代码量统计

| 成员 | 负责文件数 | 代码量 | 难度 |
|------|-----------|--------|------|
| A（后端算法） | 12个 | 约1,590行 | ⭐⭐⭐⭐⭐ |
| B（前端+数据库） | 12个 | 约1,830行 | ⭐⭐⭐⭐ |
| C（DevOps） | 13个 | 约704行 | ⭐⭐⭐ |
| **合计** | **37个** | **约4,124行** | |

---

## 八、每日站会建议

建议每天花10分钟开个简短站会：

1. 昨天完成了什么
2. 今天计划做什么
3. 遇到什么阻塞

保持信息同步，及时发现问题。

---

## 九、代码仓库管理建议

```
main分支（稳定版本）
  ├── dev分支（开发分支）
  │   ├── dev-a（成员A的开发分支）
  │   ├── dev-b（成员B的开发分支）
  │   └── dev-c（成员C的开发分支）
  └── 每天合并一次dev到main
```

- 每人在自己的dev-x分支开发
- 每天下班前合并到dev分支，解决冲突
- 第6天dev合并到main，准备演示

---

**文档版本**: v1.0
**创建日期**: 2026年5月
**适用项目**: 云计算大作业 - 基于多Agent共识的分布式邮件分类系统
