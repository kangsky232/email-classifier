# 基于 LLM Agent + Paxos 共识的分布式邮件分类系统

## 一、项目架构

```
用户浏览器 (Flask + HTML/CSS/JS)
       │
       ▼
  app.py (Flask 主应用, port 5000)
       │
       ├── 分类调度层 (agents/classifier.py)
       │      │
       │      ├── ML 对比组 (本地)
       │      │    ├── RuleAgent     (规则关键词匹配)
       │      │    ├── BayesAgent    (朴素贝叶斯 + TF-IDF)
       │      │    └── LRAgent       (逻辑回归 + TF-IDF)
       │      │
       │      └── LLM 决策组 (网络 HTTP)
       │           ├── 安全专家 (port 8503, role=security)
       │           ├── 商务助理 (port 8504, role=business)
       │           └── 通用分类 (port 8505, role=general)
       │
       └── Paxos 共识层 (paxos/coordinator.py)
              │
              ├── Acceptor-1 (port 8503, HTTP)
              ├── Acceptor-2 (port 8504, HTTP)
              └── Acceptor-3 (port 8505, HTTP)
```

### 角色定义

| 概念                  | 是什么                            | 干什么                                     |
| ------------------- | ------------------------------ | --------------------------------------- |
| **Classifier（分类器）** | ML 模型 或 LLM Agent              | 看邮件内容，给出分类意见                            |
| **Agent（智能体）**      | LLM 驱动的分类器，每个有不同 System Prompt | 从不同视角分析邮件，输出分类+置信度+推理过程                 |
| **Acceptor（接受者）**   | Paxos 协议中的投票者                  | 只比较 proposal\_id 大小，决定承诺/接受/拒绝。完全不碰邮件内容 |
| **Proposer（提议者）**   | Paxos 协议中的发起方                  | 收集 Agent 意见，向 Acceptor 发起两阶段投票          |

**关键区分**：Classifier 和 Acceptor 是两个独立角色。同一个节点进程上同时运行了分类服务和 Acceptor 服务，但逻辑完全分离。

***

## 二、核心流程

```
邮件进入
  │
  ├── 6 个分类器并行分析
  │     ├── 3 个 ML (本地): RuleAgent, BayesAgent, LRAgent  → 对比参考
  │     └── 3 个 LLM (远程): 安全专家, 商务助理, 通用分类   → 决策主体
  │
  ├── 只看 3 个 LLM Agent 的结果
  │     │
  │     ├── 3/3 或 2/3 一致 → agent_consensus，直接采纳
  │     │
  │     └── 不一致 → 触发 Paxos 共识
  │           │
  │           ├── Phase 1: Prepare
  │           │    Proposer 向 3 个 Acceptor 发送提案编号
  │           │    Acceptor 比较编号，返回 Promise 或 Reject
  │           │    需要 ≥2 个 Promise 才能继续
  │           │
  │           ├── Phase 2: Accept
  │           │    Proposer 携带完整提案内容发起确认
  │           │    Acceptor 校验编号后投票
  │           │    需要 ≥2 个 Accepted 才能达成共识
  │           │
  │           └── Learn: 共识结果被记录
  │
  └── 最终结果返回前端，写入数据库
```

### Paxos 关键机制

### **多数派原则**：3 个 Acceptor 中至少需要 2 票（3/2+1）

- **编号递增**：Acceptor 只认可编号 ≥ 已承诺编号的提案
- **冲突拒绝**：一旦承诺了更高的 proposal\_id，旧编号提案被永久拒绝
- **容错**：1 个 Acceptor 宕机，剩余 2 个仍可达成共识

***

## 三、文件结构

```
email-classifier/
├── app.py                    # Flask 主应用 (15+ REST API)
├── agent_service.py          # Acceptor 节点入口
│                               python agent_service.py --role security --port 8503 --id acceptor-1
├── config.py                 # 全局配置（含 ACCEPTOR_NODES）
├── demo_paxos.py             # Paxos 两阶段协议命令行演示
├── test_llm.py               # 端到端测试脚本
├── requirements.txt
├── init.sql                  # 数据库初始化
│
├── agents/                   # Agent 分类器模块
│   ├── base_agent.py         # Agent 抽象基类
│   ├── rule_agent.py         # 规则引擎（关键词匹配）
│   ├── bayes_agent.py        # 朴素贝叶斯
│   ├── lr_agent.py           # 逻辑回归
│   ├── llm_agent.py          # LLM Agent（DeepSeek + 三种角色 Prompt）
│   └── classifier.py         # 分类调度器（并行调度 + 共识判断）
│
├── paxos/                    # Paxos 共识算法模块
│   ├── message.py            # 消息定义（Prepare/Promise/Accept/Accepted/Reject/Learn）
│   ├── proposer.py           # 提议者（发起提案、追踪投票）
│   ├── acceptor.py           # 接受者（比较编号、投票决策）
│   ├── learner.py            # 学习者（记录结果）
│   └── coordinator.py        # 协调器（HTTP + 本地双模式）
│
├── database/                 # 数据库模块（SQLite / MySQL 双模式）
├── mq/                       # 消息队列模块（RabbitMQ）
├── docker/                   # Docker 编排（6 个容器: MySQL + RabbitMQ + App + 3 Acceptor）
├── k8s/                      # Kubernetes 部署配置 + Istio
├── static/                   # 前端资源（CSS + JS）
└── templates/                # HTML 模板
```

***

## 四、与参考视频的关系

参考视频（B站 BV1XaRtBiEh6）使用手动投票模式演示 Paxos（用户输入 y/n）。本项目做了以下改进：

| 对比项      | 参考视频              | 本项目                          |
| -------- | ----------------- | ---------------------------- |
| Paxos 投票 | 手动输入 y/n          | Agent 自动决策 + HTTP 通信         |
| 分类方式     | MapReduce + 朴素贝叶斯 | ML + LLM Agent（多视角）          |
| 存储       | GFS + 一致性哈希       | MySQL/SQLite（数据库方式）          |
| 前端       | Streamlit         | Flask + 原生 JS                |
| 部署       | 无                 | Docker + K8s + Istio         |
| 额外功能     | -                 | 消息队列、远程 Agent、WebSocket 实时推送 |

***

## 五、演示步骤

### 5.1 启动系统

需要 4 个终端：

**终端 1-3（Acceptor 节点）:**

```bash
cd email-classifier
python agent_service.py --role security  --port 8503 --id acceptor-1
python agent_service.py --role business  --port 8504 --id acceptor-2
python agent_service.py --role general   --port 8505 --id acceptor-3
```

**终端 4（主应用）:**

```bash
cd email-classifier
python app.py
```

### 5.2 配置 DeepSeek API Key

1. 浏览器打开 `http://127.0.0.1:5000`
2. 左侧导航 → **系统设置**
3. 输入 DeepSeek API Key（sk-xxx）
4. 点 **"保存并同步到节点"**，看到 3 个绿色 ✅

> 不设 Key 也可以演示，Agent 会使用关键词匹配降级模式。

### 5.3 演示 Agent 分类

1. 左侧 → **分类中心**
2. 输入邮件内容（有预填测试数据），点提交
3. 页面展示 6 个 Agent 的分类结果对比：
   - 3 个传统 ML（规则/Bayes/LR）
   - 3 个 LLM Agent（安全专家/商务助理/通用分类）
4. 每个 Agent 显示分类结果、置信度、推理过程
5. 意见一致 → 直接采纳；意见不一致 → 自动触发 Paxos

### 5.4 演示 Paxos 两阶段协议

1. 左侧 → **Paxos日志**
2. 点 **"⚡ Paxos 冲突演示"**
3. 前端实时展示三轮 Paxos 过程：
   - 第一轮 ID=1 → 通过
   - 第二轮 ID=2 → 通过（2>1）
   - 旧 ID=1 重试 → **被拒绝**（Acceptor 已承诺更高编号）
4. 清晰展示 Paxos 的 Prepare→Accept 两阶段和提案编号冲突机制

### 5.5 演示故障转移

1. 关掉终端 2（acceptor-2）
2. 再次提交分类或运行 Paxos 演示
3. 2/3 多数派仍然达成，演示分布式容错

### 5.6 其他页面

- **Agent监控**：查看所有 Agent 状态、处理量、耗时
- **分类对比**：选择已分类邮件，对比各 Agent 的投票详情
- **Paxos日志**：数据库记录的所有共识历史
- **数据统计**：分类分布图、趋势

***

## 六、技术要点

### LLM Agent 三种角色

| Agent | 角色       | System Prompt 侧重点       |
| ----- | -------- | ----------------------- |
| 安全专家  | security | 钓鱼识别、欺诈检测、链接安全、账户威胁     |
| 商务助理  | business | 会议安排、工作汇报、deadline、商务沟通 |
| 通用分类  | general  | 综合判断邮件目的、发件人身份、紧急程度     |

### Paxos 两阶段协议

1. **Prepare 阶段**：Proposer 发送 proposal\_id → Acceptor 比较编号 → 返回 Promise/Reject
2. **Accept 阶段**：Proposer 携带 value 发起确认 → Acceptor 校验 → 返回 Accepted/Reject
3. **多数派**：3 个中至少 2 个同意
4. **一致性**：Acceptor 的状态（promised\_id、accepted\_id）保证不会接受更低编号的提案

### LLM API

- 只接入 DeepSeek API（`https://api.deepseek.com/v1/chat/completions`）
- 模型：`deepseek-chat`
- 环境变量：`DEEPSEEK_API_KEY`
- 无 Key 时自动降级为关键词匹配

***

## 七、问题记录

### 概念澄清

**Q: 代码哪里"跑偏"了？**
原架构把 Classifier（分类器）、Agent（智能体）、Acceptor（Paxos 投票者）三个概念混在一起。RuleAgent/BayesAgent/LRAgent 实际上是分类模型，被错误命名成了 Agent。Paxos 是内存模拟的，没有网络通信。

**Q: Agent 到底放在哪里合适？**
Agent 放在分类层，作为 LLM 驱动的智能分类器。3 个 Agent 各自从不同专业视角分析邮件，输出结构化的分类结果。Agent 与 Acceptor 分离：Agent 负责"看懂邮件"，Acceptor 负责"投票共识"。

**Q: Agent 的作用会不会太牵强？**
对比：

- ❌ Agent 作为 Paxos 投票小工具 → 几行 if 代码就搞定，硬贴标签
- ✅ Agent 作为 LLM 分类器 → 语义理解、多步推理、可解释性、多视角分析，传统代码做不到

**Q: 视频中的 Paxos 手动投票怎么自动化？**
视频需要用户手动输入 y/n 确认。本项目通过 HTTP 调用 Acceptor 的 `/paxos/prepare` 和 `/paxos/accept` 端点实现自动化。Acceptor 自动比较提案编号，返回决定。

### 设计决策

- Paxos coordinator 支持双模式：HTTP 远程（分布式演示）和本地内存（开发测试）
- 分类调度器同时运行 ML 和 LLM 两套 Agent，ML 作为对比参考，LLM 作为决策主体
- 3 个节点共享进程运行 Classifier + Acceptor，逻辑分离但部署在同一进程，减少终端数量

