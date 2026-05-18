from infrastructure.database.models import Classification, FinalResult, PaxosLog
from config.settings import Config
from infrastructure.cluster.consistent_hash import cluster_manager
from infrastructure.cloud_native.tracing import tracer
from infrastructure.cloud_native.circuit_breaker import circuit_breaker
from infrastructure.cluster.load_balancer import load_balancer
import requests
import concurrent.futures
import threading
import time
import logging
from collections import Counter
from flask import g

logger = logging.getLogger(__name__)


class AcceptorNodeAgent:
    """LLM Agent 节点"""

    def __init__(self, node_config):
        self.id = node_config["id"]
        self.name = node_config["name"]
        self.role = node_config["role"]
        self.url = node_config["url"]
        self.status = "checking"
        self.processed_count = 0
        self.total_time = 0
        self.last_check = 0
        self._consecutive_failures = 0
        self._lock = threading.Lock()

    @property
    def method(self):
        return f"llm_{self.role}"

    def check_health(self):
        try:
            resp = requests.get(f"{self.url}/health", timeout=2)
            if resp.status_code == 200:
                self.status = "online"
                self.last_check = time.time()
                self._consecutive_failures = 0
                cluster_manager.update_heartbeat(self.id)
                return resp.json()
        except Exception:
            pass

        self._consecutive_failures += 1
        self.status = "offline"
        self.last_check = time.time()

        # 连续失败3次才报告故障
        if self._consecutive_failures >= 3:
            cluster_manager.report_failure(self.id)

        return None

    def is_available(self):
        return self.status == "online"

    def classify(self, sender, subject, content):
        start = time.time()
        headers = {}
        try:
            trace_id = g.trace_id
        except (RuntimeError, AttributeError):
            trace_id = None
        if trace_id:
            headers['X-Trace-Id'] = trace_id
        try:
            resp = requests.post(
                f"{self.url}/classify",
                json={"sender": sender, "subject": subject, "content": content},
                headers=headers,
                timeout=30
            )
            elapsed = round((time.time() - start) * 1000, 2)
            with self._lock:
                self.total_time += elapsed
                self.processed_count += 1
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    self.status = "online"
                    return data["result"]
        except Exception:
            elapsed = round((time.time() - start) * 1000, 2)
            with self._lock:
                self.total_time += elapsed
                self.processed_count += 1
            self.status = "offline"
        return None

    def vote(self, content, proposed_category, proposed_reason):
        """判断是否同意提议的分类"""
        start = time.time()
        headers = {}
        try:
            trace_id = g.trace_id
        except (RuntimeError, AttributeError):
            trace_id = None
        if trace_id:
            headers['X-Trace-Id'] = trace_id
        try:
            resp = requests.post(
                f"{self.url}/paxos/vote",
                json={
                    "content": content,
                    "proposed_category": proposed_category,
                    "proposed_reason": proposed_reason
                },
                headers=headers,
                timeout=30
            )
            elapsed = round((time.time() - start) * 1000, 2)
            with self._lock:
                self.total_time += elapsed
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data.get("vote", {"agree": False})
        except Exception as e:
            logger.warning(f"Vote request failed for {self.name}: {e}")
        return {"agree": False, "reason": "请求失败"}

    def get_stats(self):
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
    _classify_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="classify")
    _vote_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="vote")

    def __init__(self):
        self.acceptor_nodes = [
            AcceptorNodeAgent(cfg) for cfg in Config.ACCEPTOR_NODES
        ]

        # 注册节点到集群管理器和负载均衡器
        for node in self.acceptor_nodes:
            cluster_manager.register_node(node.id, {
                "name": node.name,
                "role": node.role,
                "url": node.url
            })
            load_balancer.register_node(node.id, weight=1)

        # 启动健康检查
        cluster_manager.start_health_check(check_interval=10)

        # 启动后台健康检查线程（缓存结果，避免API阻塞）
        self._start_background_health_check()

    def _start_background_health_check(self):
        """启动后台线程，定期检查所有节点健康状态并缓存"""
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(self.acceptor_nodes))

        def _check_loop():
            while True:
                try:
                    list(self._executor.map(lambda n: n.check_health(), self.acceptor_nodes))
                except Exception as e:
                    logger.debug(f"Background health check error: {e}")
                time.sleep(8)

        t = threading.Thread(target=_check_loop, daemon=True)
        t.start()
        logger.info("Background health check thread started")

    def get_all_agents(self):
        return list(self.acceptor_nodes)

    def _classify_with_node(self, node, sender, subject, content):
        start = time.time()
        breaker = circuit_breaker.get_or_create(
            f"agent-{node.id}", failure_threshold=5, recovery_timeout=30
        )
        try:
            result = breaker.call(lambda: node.classify(sender, subject, content))
        except Exception:
            elapsed = (time.time() - start) * 1000
            load_balancer.record_request(node.id, elapsed, False)
            return None
        elapsed = (time.time() - start) * 1000
        if result:
            load_balancer.record_request(node.id, elapsed, True)
            return {
                "agent_name": node.name,
                "method": node.method,
                "role": node.role,
                "category": result["category"],
                "confidence": result["confidence"],
                "reason": result.get("reason", ""),
                "keywords": result.get("keywords", []),
                "node_url": node.url
            }
        load_balancer.record_request(node.id, elapsed, False)
        return None

    def classify(self, email_id, sender, subject, content):
        """分类流程：4个Agent各自分类 → 取最高置信度作为Proposer → 其他Agent投票 → Paxos共识"""
        logger.info(f"开始分类 email_id={email_id}, sender={sender}")
        all_results = []
        nodes_available = []

        for node in self.acceptor_nodes:
            if node.is_available():
                nodes_available.append(node)

        if not nodes_available:
            logger.warning("无可用 LLM Agent 节点")
            return {"success": False, "message": "无可用 LLM Agent 节点，请先启动 agent_service", "agents": [], "paxos_log": []}

        # 获取当前 trace span 作为父 span
        parent_span = getattr(g, 'span', None)

        # 第一阶段：所有Agent各自分类
        agent_span = tracer.start_span("classify.agents", "gateway", parent_span)
        agent_span.set_tag("agent_count", len(nodes_available))
        futures = {
            self._classify_pool.submit(self._classify_with_node, node, sender, subject, content): node
            for node in nodes_available
        }

        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
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
            except Exception as e:
                err_result = {
                    "agent_name": node.name,
                    "method": node.method,
                    "category": "错误",
                    "confidence": 0,
                    "reason": str(e),
                    "error": str(e)
                }
                all_results.append(err_result)

        valid_results = [r for r in all_results if r.get("category") != "错误"]
        agent_span.set_tag("valid_results", len(valid_results))
        agent_span.finish()

        if not valid_results:
            return {"success": False, "message": "所有 LLM Agent 分类失败", "agents": all_results, "paxos_log": []}

        # 第二阶段：取置信度最高的作为Proposer
        proposer = max(valid_results, key=lambda r: r.get("confidence", 0))
        proposed_category = proposer["category"]
        proposed_reason = proposer.get("reason", "")

        logger.info(f"email_id={email_id} Proposer: {proposer['agent_name']} 提议: {proposed_category}")

        # 第三阶段：其他Agent投票
        vote_span = tracer.start_span("paxos.vote", "gateway", parent_span)
        vote_span.set_tag("proposer", proposer["agent_name"])
        vote_span.set_tag("proposed_category", proposed_category)
        paxos_log = [{
            "phase": "propose",
            "agent": proposer["agent_name"],
            "category": proposed_category,
            "confidence": proposer["confidence"],
            "reason": proposed_reason
        }]

        acceptors = [n for n in nodes_available if n.name != proposer["agent_name"]]
        votes = []

        def _vote_with_breaker(node):
            start = time.time()
            breaker = circuit_breaker.get_or_create(
                f"agent-{node.id}", failure_threshold=3, recovery_timeout=30
            )
            try:
                result = breaker.call(lambda: node.vote(f"{sender}\n{subject}\n{content}", proposed_category, proposed_reason))
                elapsed = (time.time() - start) * 1000
                load_balancer.record_request(node.id, elapsed, True)
                return result
            except Exception:
                elapsed = (time.time() - start) * 1000
                load_balancer.record_request(node.id, elapsed, False)
                return {"agree": False, "reason": "熔断器开启"}

        futures = {
            self._vote_pool.submit(_vote_with_breaker, node): node
            for node in acceptors
        }

        for future in concurrent.futures.as_completed(futures):
            node = futures[future]
            try:
                vote_result = future.result()
                votes.append({
                    "agent_name": node.name,
                    "agree": vote_result.get("agree", False),
                    "reason": vote_result.get("reason", "")
                })
                paxos_log.append({
                    "phase": "vote",
                    "agent": node.name,
                    "agree": vote_result.get("agree", False),
                    "reason": vote_result.get("reason", "")
                })
            except Exception as e:
                votes.append({
                    "agent_name": node.name,
                    "agree": False,
                    "reason": str(e)
                })

        vote_span.set_tag("agree_count", sum(1 for v in votes if v["agree"]))
        vote_span.set_tag("total_voters", len(votes))
        vote_span.finish()

        # 第四阶段：统计投票结果
        consensus_span = tracer.start_span("paxos.consensus", "gateway", parent_span)
        agree_count = sum(1 for v in votes if v["agree"])
        total_voters = len(votes)
        need_majority = (total_voters // 2) + 1

        if agree_count >= need_majority:
            # 多数同意，采纳提议
            final_category = proposed_category
            method = "paxos_consensus"
            message = f"Paxos 共识达成: {final_category} ({agree_count}/{total_voters} 同意)"
            paxos_log.append({"phase": "consensus", "result": "accepted", "category": final_category})
        else:
            # 未达成共识，取多数投票
            categories = [r["category"] for r in valid_results]
            counter = Counter(categories)
            final_category = counter.most_common(1)[0][0]
            method = "majority_vote"
            message = f"未达成共识，采用多数投票: {final_category}"
            paxos_log.append({"phase": "consensus", "result": "fallback", "category": final_category})

        consensus_span.set_tag("method", method)
        consensus_span.set_tag("final_category", final_category)
        consensus_span.finish()

        FinalResult.create(email_id, final_category, method)

        # 持久化 Paxos 日志到数据库
        proposal_id = f"p{email_id}-{int(time.time())}"
        PaxosLog.create(email_id, proposal_id, "propose",
                        proposer["agent_name"], proposed_category, "proposed",
                        acceptor_votes=None)
        for v in votes:
            PaxosLog.create(email_id, proposal_id, "vote",
                            v["agent_name"], proposed_category,
                            "agree" if v["agree"] else "reject",
                            acceptor_votes={"reason": v.get("reason", "")})
        PaxosLog.create(email_id, proposal_id, "consensus",
                        "system", final_category, method,
                        acceptor_votes={"agree": agree_count, "total": total_voters})

        logger.info(f"email_id={email_id} 分类完成: {final_category} (method={method})")

        return {
            "success": True,
            "email_id": email_id,
            "final_category": final_category,
            "method": method,
            "agents": all_results,
            "votes": votes,
            "paxos_log": paxos_log,
            "message": message
        }

    def get_agents_status(self):
        futures = [self._executor.submit(a.get_stats) for a in self.get_all_agents()]
        return [f.result() for f in concurrent.futures.as_completed(futures)]

    def get_agents_stats(self):
        stats = Classification.get_agent_stats()
        futures = [self._executor.submit(a.get_stats) for a in self.get_all_agents()]
        agents = [f.result() for f in concurrent.futures.as_completed(futures)]
        return {
            "agents": agents,
            "performance": stats
        }


classifier = EmailClassifier()
