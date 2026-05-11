from agents.rule_agent import RuleAgent
from agents.bayes_agent import BayesAgent
from agents.lr_agent import LRAgent
from agents.llm_agent import LLMAgent
from paxos.coordinator import PaxosCoordinator
from database.models import Classification, FinalResult
from config import Config
import requests
import concurrent.futures
import time

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
        except:
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

class EmailClassifier:
    def __init__(self):
        self.local_agents = [
            RuleAgent(),
            BayesAgent(),
            LRAgent(),
            LLMAgent()
        ]
        self.remote_agents = []
        self.consensus_threshold = 0.6
        self._load_remote_agents()
    
    def _load_remote_agents(self):
        remote_configs = Config.REMOTE_AGENTS
        for cfg in remote_configs:
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
        return self.local_agents + self.remote_agents
    
    def _get_available_agents(self):
        available = list(self.local_agents)
        for agent in self.remote_agents:
            if agent.is_available():
                available.append(agent)
        return available
    
    def _classify_with_agent(self, agent, sender, subject, content):
        if isinstance(agent, RemoteAgent):
            result = agent.classify(sender, subject, content)
            return {
                "agent_name": agent.name,
                "method": agent.method,
                "category": result["category"],
                "confidence": result["confidence"],
                "details": result,
                "is_remote": True,
                "url": agent.url
            }
        else:
            result = agent.classify(sender, subject, content)
            return {
                "agent_name": agent.name,
                "method": agent.method,
                "category": result["category"],
                "confidence": result["confidence"],
                "details": result,
                "is_remote": False
            }
    
    def classify(self, email_id, sender, subject, content):
        all_agents = self._get_available_agents()
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_agents)) as executor:
            futures = {
                executor.submit(self._classify_with_agent, agent, sender, subject, content): agent
                for agent in all_agents
            }
            for future in concurrent.futures.as_completed(futures):
                agent = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    Classification.create(
                        email_id=email_id,
                        agent_name=result["agent_name"],
                        method=result["method"],
                        category=result["category"],
                        confidence=result["confidence"]
                    )
                except Exception as e:
                    results.append({
                        "agent_name": agent.name,
                        "method": getattr(agent, 'method', 'unknown'),
                        "category": "错误",
                        "confidence": 0,
                        "error": str(e),
                        "is_remote": isinstance(agent, RemoteAgent)
                    })
        
        categories = [r["category"] for r in results if r["category"] != "错误"]
        
        if not categories:
            return {
                "success": False,
                "message": "所有Agent分类失败",
                "agents": results,
                "paxos_log": []
            }
        
        from collections import Counter
        counter = Counter(categories)
        most_common = counter.most_common(1)[0]
        total_agents = len([r for r in results if r["category"] != "错误"])
        need_majority = (total_agents // 2) + 1
        
        if most_common[1] >= need_majority:
            final_category = most_common[0]
            method = "agent_consensus"
            
            FinalResult.create(email_id, final_category, method)
            
            return {
                "success": True,
                "email_id": email_id,
                "final_category": final_category,
                "method": method,
                "agents": results,
                "paxos_log": [],
                "message": f"Agent投票一致 ({most_common[1]}/{total_agents})，直接采纳"
            }
        else:
            coordinator = PaxosCoordinator(
                num_acceptors=Config.PAXOS_ACCEPTOR_COUNT,
                email_id=email_id
            )
            
            best_result = max(results, key=lambda r: r["confidence"] if r["category"] != "错误" else 0)
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
                    "agents": results,
                    "paxos_log": paxos_result.get("log", []),
                    "elapsed_ms": paxos_result.get("elapsed_ms", 0),
                    "message": f"Paxos共识达成，最终分类: {final_category}"
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
                    "agents": results,
                    "paxos_log": paxos_result.get("log", []),
                    "message": f"Paxos共识失败，采用最高置信度结果: {final_category}"
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
