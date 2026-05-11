from paxos.proposer import Proposer
from paxos.acceptor import Acceptor
from paxos.learner import Learner
from paxos.message import Message
from database.models import PaxosLog
import time
import uuid

class PaxosCoordinator:
    def __init__(self, num_acceptors=3, email_id=None):
        self.email_id = email_id
        self.proposer = Proposer()
        self.acceptors = [Acceptor(f"acceptor-{i}") for i in range(num_acceptors)]
        self.learner = Learner("learner-0")
        self.num_acceptors = num_acceptors
        self.log = []
        self.result = None
        self.consensus_reached = False
    
    def run_consensus(self, value):
        self.log = []
        start_time = time.time()
        
        self._log_event("start", f"开始共识流程，提议值: {value}")
        
        prepare_msg = self.proposer.propose(value)
        self._log_event("prepare", f"Proposer发送Prepare请求，编号: {prepare_msg.proposal_id}")
        
        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=prepare_msg.proposal_id,
                phase="prepare",
                proposer=self.proposer.id,
                value=value,
                result="pending"
            )
        
        promises = []
        for acceptor in self.acceptors:
            response = acceptor.handle_prepare(prepare_msg)
            if response.type.value == "promise":
                promises.append(response)
                self._log_event("promise", f"Acceptor {acceptor.id} 承诺 Promise")
            else:
                self._log_event("reject", f"Acceptor {acceptor.id} 拒绝 Prepare")
        
        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=prepare_msg.proposal_id,
                phase="promise",
                proposer=self.proposer.id,
                value=value,
                result=f"{len(promises)}/{self.num_acceptors}",
                acceptor_votes=[p.to_dict() for p in promises]
            )
        
        majority = (self.num_acceptors // 2) + 1
        if len(promises) < majority:
            self._log_event("fail", f"Prepare阶段失败，未获得多数派承诺 ({len(promises)}/{self.num_acceptors})")
            if self.email_id:
                PaxosLog.create(
                    email_id=self.email_id,
                    proposal_id=prepare_msg.proposal_id,
                    phase="learn",
                    proposer=self.proposer.id,
                    value=value,
                    result="failed"
                )
            return {"success": False, "reason": "未获得多数派承诺", "log": self.log}
        
        for promise in promises:
            self.proposer.handle_promise(promise)
        
        accept_msg = self.proposer.create_accept_message()
        self._log_event("accept", f"Proposer发送Accept请求，值: {accept_msg.value}")
        
        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=accept_msg.proposal_id,
                phase="accept",
                proposer=self.proposer.id,
                value=accept_msg.value,
                result="pending"
            )
        
        accepteds = []
        for acceptor in self.acceptors:
            response = acceptor.handle_accept(accept_msg)
            if response.type.value == "accepted":
                accepteds.append(response)
                self._log_event("accepted", f"Acceptor {acceptor.id} 接受 Accept")
            else:
                self._log_event("reject", f"Acceptor {acceptor.id} 拒绝 Accept")
        
        if self.email_id:
            PaxosLog.create(
                email_id=self.email_id,
                proposal_id=accept_msg.proposal_id,
                phase="accepted",
                proposer=self.proposer.id,
                value=accept_msg.value,
                result=f"{len(accepteds)}/{self.num_acceptors}",
                acceptor_votes=[a.to_dict() for a in accepteds]
            )
        
        if len(accepteds) < majority:
            self._log_event("fail", f"Accept阶段失败，未获得多数派接受 ({len(accepteds)}/{self.num_acceptors})")
            if self.email_id:
                PaxosLog.create(
                    email_id=self.email_id,
                    proposal_id=accept_msg.proposal_id,
                    phase="learn",
                    proposer=self.proposer.id,
                    value=accept_msg.value,
                    result="failed"
                )
            return {"success": False, "reason": "未获得多数派接受", "log": self.log}
        
        for accepted in accepteds:
            self.proposer.handle_accepted(accepted)
        
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
    
    def _log_event(self, event_type, message):
        self.log.append({
            "type": event_type,
            "message": message,
            "timestamp": time.time()
        })
    
    def get_result(self):
        return self.result
