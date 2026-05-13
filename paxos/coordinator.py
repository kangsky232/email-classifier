from paxos.proposer import Proposer
from paxos.acceptor import Acceptor
from paxos.learner import Learner
from paxos.message import Message
from database.models import PaxosLog
import requests
import time

class PaxosCoordinator:
    def __init__(self, acceptor_urls, email_id=None):
        self.email_id = email_id
        self.acceptor_urls = acceptor_urls
        self.num_acceptors = len(acceptor_urls)
        self.proposer = Proposer()
        self.learner = Learner("learner-0")
        self.log = []
        self.result = None
        self.consensus_reached = False
        self._local_acceptors = None

    @property
    def is_local_mode(self):
        return self.acceptor_urls and self.acceptor_urls[0].startswith("local://")

    def _get_local_acceptors(self):
        if self._local_acceptors is None:
            self._local_acceptors = [
                Acceptor(f"acceptor-{i}") for i in range(self.num_acceptors)
            ]
        return self._local_acceptors

    def run_consensus(self, value):
        self.log = []
        start_time = time.time()

        self._log_event("start", f"开始 Paxos 共识流程，提议值: {value}")

        prepare_msg = self.proposer.propose(value)
        mode_tag = "[本地]" if self.is_local_mode else "[HTTP]"
        self._log_event("prepare", f"{mode_tag} Proposer 发送 Prepare 请求，提案编号: {prepare_msg.proposal_id}")

        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=prepare_msg.proposal_id,
                phase="prepare",
                proposer=self.proposer.id,
                value=value,
                result="pending"
            )

        if self.is_local_mode:
            promises = self._local_prepare_phase(prepare_msg)
        else:
            promises = self._http_prepare_phase(prepare_msg)

        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=prepare_msg.proposal_id,
                phase="promise",
                proposer=self.proposer.id,
                value=value,
                result=f"{len(promises)}/{self.num_acceptors}",
                acceptor_votes=[p.to_dict() for p in promises] if not self.is_local_mode else []
            )

        majority = (self.num_acceptors // 2) + 1
        if len(promises) < majority:
            self._log_event("fail", f"Prepare 阶段失败 ({len(promises)}/{self.num_acceptors})")
            if self.email_id:
                PaxosLog.create(
                    email_id=self.email_id,
                    proposal_id=prepare_msg.proposal_id,
                    phase="learn",
                    proposer=self.proposer.id,
                    value=value,
                    result="failed"
                )
            return {
                "success": False,
                "reason": f"Prepare 阶段未获多数派 ({len(promises)}/{self.num_acceptors})",
                "log": self.log
            }

        for promise in promises:
            if self.is_local_mode:
                self.proposer.handle_promise(promise)
            else:
                m = Message(
                    msg_type=promise["type"],
                    proposal_id=promise["proposal_id"],
                    acceptor_id=promise.get("acceptor_id"),
                    accepted_id=promise.get("accepted_id"),
                    accepted_value=promise.get("accepted_value")
                )
                self.proposer.handle_promise(m)

        accept_msg = self.proposer.create_accept_message()
        self._log_event("accept", f"{mode_tag} Proposer 发送 Accept 请求，值: {accept_msg.value}")

        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=accept_msg.proposal_id,
                phase="accept",
                proposer=self.proposer.id,
                value=accept_msg.value,
                result="pending"
            )

        if self.is_local_mode:
            accepteds = self._local_accept_phase(accept_msg)
        else:
            accepteds = self._http_accept_phase(accept_msg)

        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=accept_msg.proposal_id,
                phase="accepted",
                proposer=self.proposer.id,
                value=accept_msg.value,
                result=f"{len(accepteds)}/{self.num_acceptors}",
                acceptor_votes=[a.to_dict() for a in accepteds] if not self.is_local_mode else []
            )

        if len(accepteds) < majority:
            self._log_event("fail", f"Accept 阶段失败 ({len(accepteds)}/{self.num_acceptors})")
            if self.email_id:
                PaxosLog.create(
                    email_id=self.email_id,
                    proposal_id=accept_msg.proposal_id,
                    phase="learn",
                    proposer=self.proposer.id,
                    value=accept_msg.value,
                    result="failed"
                )
            return {
                "success": False,
                "reason": f"Accept 阶段未获多数派 ({len(accepteds)}/{self.num_acceptors})",
                "log": self.log
            }

        for accepted in accepteds:
            if self.is_local_mode:
                self.proposer.handle_accepted(accepted)
            else:
                m = Message(
                    msg_type=accepted["type"],
                    proposal_id=accepted["proposal_id"],
                    value=accepted.get("value"),
                    acceptor_id=accepted.get("acceptor_id")
                )
                self.proposer.handle_accepted(m)

        final_value = self.proposer.get_final_value()
        learn_msg = Message.create_learn(final_value)
        self.learner.learn(learn_msg)

        self.result = final_value
        self.consensus_reached = True

        elapsed = round((time.time() - start_time) * 1000, 2)
        self._log_event("learn", f"共识达成！最终值: {final_value}，耗时: {elapsed}ms")

        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=accept_msg.proposal_id,
                phase="learn",
                proposer=self.proposer.id,
                value=final_value,
                result="success"
            )

        return {
            "success": True,
            "value": final_value,
            "elapsed_ms": elapsed,
            "log": self.log,
            "votes": {
                "prepare_responses": len(promises),
                "accept_responses": len(accepteds),
                "total_acceptors": self.num_acceptors
            }
        }

    def _local_prepare_phase(self, prepare_msg):
        promises = []
        for acceptor in self._get_local_acceptors():
            response = acceptor.handle_prepare(prepare_msg)
            if response.type.value == "promise":
                promises.append(response)
                self._log_event("promise", f"Acceptor [{acceptor.id}] 承诺 Promise")
            else:
                self._log_event("reject_prepare", f"Acceptor [{acceptor.id}] 拒绝 Prepare")
        return promises

    def _local_accept_phase(self, accept_msg):
        accepteds = []
        for acceptor in self._get_local_acceptors():
            response = acceptor.handle_accept(accept_msg)
            if response.type.value == "accepted":
                accepteds.append(response)
                self._log_event("accepted", f"Acceptor [{acceptor.id}] 接受 Accept")
            else:
                self._log_event("reject_accept", f"Acceptor [{acceptor.id}] 拒绝 Accept")
        return accepteds

    def _http_prepare_phase(self, prepare_msg):
        promises = []
        for url in self.acceptor_urls:
            try:
                resp = requests.post(
                    f"{url}/paxos/prepare",
                    json={
                        "proposal_id": prepare_msg.proposal_id,
                        "sender": self.proposer.id
                    },
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("type") == "promise":
                        promises.append(data)
                        self._log_event("promise", f"Acceptor [{url}] 返回 Promise")
                    else:
                        self._log_event("reject_prepare", f"Acceptor [{url}] 拒绝: {data.get('reason', '')}")
                else:
                    self._log_event("reject_prepare", f"Acceptor [{url}] HTTP {resp.status_code}")
            except Exception as e:
                self._log_event("reject_prepare", f"Acceptor [{url}] 无响应 ({str(e)[:50]})")
        return promises

    def _http_accept_phase(self, accept_msg):
        accepteds = []
        for url in self.acceptor_urls:
            try:
                resp = requests.post(
                    f"{url}/paxos/accept",
                    json={
                        "proposal_id": accept_msg.proposal_id,
                        "value": accept_msg.value,
                        "sender": self.proposer.id
                    },
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("type") == "accepted":
                        accepteds.append(data)
                        self._log_event("accepted", f"Acceptor [{url}] 接受 Accept")
                    else:
                        self._log_event("reject_accept", f"Acceptor [{url}] 拒绝: {data.get('reason', '')}")
                else:
                    self._log_event("reject_accept", f"Acceptor [{url}] HTTP {resp.status_code}")
            except Exception as e:
                self._log_event("reject_accept", f"Acceptor [{url}] 无响应 ({str(e)[:50]})")
        return accepteds

    def _log_event(self, event_type, message):
        self.log.append({
            "type": event_type,
            "message": message,
            "timestamp": time.time()
        })

    def get_result(self):
        return self.result
