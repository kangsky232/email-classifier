from agents.rule_agent import RuleAgent
from agents.bayes_agent import BayesAgent
from agents.lr_agent import LRAgent
from paxos.coordinator import PaxosCoordinator
from database.models import Classification, FinalResult
from config import Config
import requests
import concurrent.futures
import time
from collections import Counter


class RemoteAgent:
    def __init__(self, name, method, url, timeout=10):
        self.name = name
        self.method = method
        self.url = url
        self.timeout = timeout
        self.status = "checking"
        self.processed_count = 0
        self.total_time = 0
        self.last_check = 0

    def check_health(self):
        try:
            resp = requests.get(f"{self.url}/health", timeout=3)
            if resp.status_code == 200:
                self.status = "online"
                self.last_check = time.time()
                return True
        except Exception:
            pass
        self.status = "offline"
        self.last_check = time.time()
        return False

    def is_available(self):
        if time.time() - self.last_check > 30:
            self.check_health()
        return self.status == "online"

    def classify(self, sender, subject, content):
        start = time.time()
        try:
            resp = requests.post(
                f"{self.url}/classify",
                json={"sender": sender, "subject": subject, "content": content},
                timeout=self.timeout
            )
            elapsed = round((time.time() - start) * 1000, 2)
            self.total_time += elapsed
            self.processed_count += 1
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    self.status = "online"
                    return data["result"]
            raise Exception(f"远程Agent响应异常: {resp.status_code}")
        except Exception as e:
            elapsed = round((time.time() - start) * 1000, 2)
            self.total_time += elapsed
            self.processed_count += 1
            if "Connection" in str(e) or "timeout" in str(e).lower():
                self.status = "offline"
            raise e

    def get_stats(self):
        if time.time() - self.last_check > 10:
            self.check_health()
        avg_time = round(self.total_time / self.processed_count, 2) if self.processed_count > 0 else 0
        return {
            "id": f"remote-{self.url.split(':')[-1]}",
            "name": self.name,
            "method": self.method,
            "status": self.status,
            "processed_count": self.processed_count,
            "avg_time_ms": avg_time,
            "url": self.url
        }


class AcceptorNodeAgent:
    """封装对 Acceptor 节点的调用，既是 Agent 分类器也是 Paxos 投票者"""

    def __init__(self, node_config):
        self.id = node_config["id"]
        self.name = node_config["name"]
        self.role = node_config["role"]
        self.url = node_config["url"]
        self.status = "checking"
        self.processed_count = 0
        self.total_time = 0
        self.last_check = 0

    @property
    def method(self):
        return f"llm_{self.role}"

    def check_health(self):
        try:
            resp = requests.get(f"{self.url}/health", timeout=3)
            if resp.status_code == 200:
                self.status = "online"
                self.last_check = time.time()
                return resp.json()
        except Exception:
            pass
        self.status = "offline"
        self.last_check = time.time()
        return None

    def is_available(self):
        if time.time() - self.last_check > 30:
            self.check_health()
        return self.status == "online"

    def classify(self, sender, subject, content):
        start = time.time()
        try:
            resp = requests.post(
                f"{self.url}/classify",
                json={"sender": sender, "subject": subject, "content": content},
                timeout=15
            )
            elapsed = round((time.time() - start) * 1000, 2)
            self.total_time += elapsed
            self.processed_count += 1
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    self.status = "online"
                    return data["result"]
        except Exception:
            elapsed = round((time.time() - start) * 1000, 2)
            self.total_time += elapsed
            self.processed_count += 1
            self.status = "offline"
        return None

    def get_stats(self):
        if time.time() - self.last_check > 10:
            self.check_health()
        avg_time = round(self.total_time / self.processed_count, 2) if self.processed_count > 0 else 0
        return {
            "id": self.id,
            "name": self.name,
            "method": self.method,
            "role": self.role,
            "status": self.status,
            "processed_count": self.processed_count,
            "avg_time_ms": avg_time,
            "url": self.url
        }


class EmailClassifier:
    def __init__(self):
        self.local_agents = [
            RuleAgent(),
            BayesAgent(),
            LRAgent()
        ]
        self.acceptor_nodes = [
            AcceptorNodeAgent(cfg) for cfg in Config.ACCEPTOR_NODES
        ]
        self.remote_agents = []
        self._load_remote_agents()

    def _load_remote_agents(self):
        for cfg in Config.REMOTE_AGENTS:
            agent = RemoteAgent(
                name=cfg.get("name", "Remote"),
                method=cfg.get("method", "remote"),
                url=cfg.get("url", ""),
                timeout=cfg.get("timeout", 10)
            )
            self.remote_agents.append(agent)

    def add_remote_agent(self, name, method, url, timeout=10):
        agent = RemoteAgent(name, method, url, timeout)
        self.remote_agents.append(agent)
        return agent.get_stats()

    def remove_remote_agent(self, url):
        self.remote_agents = [a for a in self.remote_agents if a.url != url]

    def get_all_agents(self):
        all_agents = list(self.local_agents)
        all_agents.extend(self.acceptor_nodes)
        all_agents.extend(self.remote_agents)
        return all_agents

    def _nodes_available(self):
        return any(n.is_available() for n in self.acceptor_nodes)

    def _classify_with_node(self, node, sender, subject, content):
        result = node.classify(sender, subject, content)
        if result:
            return {
                "agent_name": node.name,
                "method": node.method,
                "role": node.role,
                "category": result["category"],
                "confidence": result["confidence"],
                "keywords": result.get("keywords", []),
                "details": result,
                "is_remote": False,
                "is_acceptor_node": True,
                "node_url": node.url
            }
        return None

    def _classify_with_local_agent(self, agent, sender, subject, content):
        result = agent.classify(sender, subject, content)
        return {
            "agent_name": agent.name,
            "method": agent.method,
            "category": result["category"],
            "confidence": result["confidence"],
            "keywords": result.get("keywords", []),
            "details": result,
            "is_remote": False,
            "is_acceptor_node": False,
            "is_ml": True
        }

    def classify(self, email_id, sender, subject, content):
        # 同时跑所有 Agent（ML + LLM），用于对比展示
        all_results = []
        llm_results = []
        nodes_available = []

        all_tasks = []
        for agent in self.local_agents:
            all_tasks.append(("ml", agent, None))
        for node in self.acceptor_nodes:
            if node.is_available():
                all_tasks.append(("llm", None, node))
                nodes_available.append(node)

        if not all_tasks:
            return {"success": False, "message": "无可用 Agent", "agents": [], "paxos_log": []}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_tasks)) as executor:
            futures = {}
            for task_type, agent, node in all_tasks:
                if task_type == "ml":
                    futures[executor.submit(self._classify_with_local_agent, agent, sender, subject, content)] = (task_type, agent, None)
                else:
                    futures[executor.submit(self._classify_with_node, node, sender, subject, content)] = (task_type, None, node)

            for future in concurrent.futures.as_completed(futures):
                task_type, agent, node = futures[future]
                try:
                    result = future.result()
                    if result:
                        all_results.append(result)
                        Classification.create(
                            email_id=email_id,
                            agent_name=result["agent_name"],
                            method=result["method"],
                            category=result["category"],
                            confidence=result["confidence"]
                        )
                        if task_type == "llm":
                            llm_results.append(result)
                except Exception as e:
                    name = agent.name if agent else node.name if node else "unknown"
                    err_result = {
                        "agent_name": name,
                        "method": getattr(agent or node, 'method', 'unknown'),
                        "category": "错误",
                        "confidence": 0,
                        "error": str(e),
                        "is_acceptor_node": task_type == "llm",
                        "is_ml": task_type == "ml"
                    }
                    all_results.append(err_result)

        if not all_results:
            return {"success": False, "message": "所有 Agent 分类失败", "agents": [], "paxos_log": []}

        # 共识判断：只用 LLM Agent 的结果
        # 如果没有 LLM 节点，则退回到用 ML 结果
        decision_results = llm_results if llm_results else [r for r in all_results if r.get("is_ml", False)]
        if not decision_results:
            decision_results = [r for r in all_results if r["category"] != "错误"]

        categories = [r["category"] for r in decision_results if r["category"] != "错误"]
        if not categories:
            return {"success": False, "message": "所有 Agent 分类失败", "agents": all_results, "paxos_log": []}

        counter = Counter(categories)
        most_common = counter.most_common(1)[0]
        total = len(categories)
        need_majority = (total // 2) + 1

        # LLM 意见一致 → 直接采纳
        if most_common[1] >= need_majority:
            final_category = most_common[0]
            method = "agent_consensus"
            FinalResult.create(email_id, final_category, method)
            return {
                "success": True,
                "email_id": email_id,
                "final_category": final_category,
                "method": method,
                "agents": all_results,
                "paxos_log": [],
                "message": f"{'LLM' if llm_results else 'ML'} Agent 一致 ({most_common[1]}/{total})，直接采纳"
            }

        # 不一致 → 触发 Paxos
        if nodes_available:
            coordinator = PaxosCoordinator(
                acceptor_urls=[n.url for n in nodes_available],
                email_id=email_id
            )
        else:
            coordinator = PaxosCoordinator(
                acceptor_urls=[f"local://acceptor-{i}" for i in range(Config.PAXOS_ACCEPTOR_COUNT)],
                email_id=email_id
            )

        best_result = max(decision_results, key=lambda r: r["confidence"] if r["category"] != "错误" else 0)
        paxos_result = coordinator.run_consensus(best_result["category"])

        if paxos_result["success"]:
            final_category = paxos_result["value"]
            method = "paxos_consensus"
            FinalResult.create(email_id, final_category, method)
            return {
                "success": True,
                "email_id": email_id,
                "final_category": final_category,
                "method": method,
                "agents": all_results,
                "paxos_log": paxos_result.get("log", []),
                "elapsed_ms": paxos_result.get("elapsed_ms", 0),
                "message": f"Paxos 共识达成，最终分类: {final_category}"
            }
        else:
            final_category = best_result["category"]
            method = "fallback"
            FinalResult.create(email_id, final_category, method)
            return {
                "success": True,
                "email_id": email_id,
                "final_category": final_category,
                "method": method,
                "agents": all_results,
                "paxos_log": paxos_result.get("log", []),
                "message": f"Paxos 共识失败，采用最高置信度结果: {final_category}"
            }

    def get_agents_status(self):
        return [a.get_stats() for a in self.get_all_agents()]

    def get_agents_stats(self):
        stats = Classification.get_agent_stats()
        return {
            "agents": [a.get_stats() for a in self.get_all_agents()],
            "performance": stats
        }


classifier = EmailClassifier()
