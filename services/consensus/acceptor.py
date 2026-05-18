from services.consensus.message import Message, MessageType
import threading
import logging

logger = logging.getLogger(__name__)

class Acceptor:
    def __init__(self, acceptor_id):
        self.id = acceptor_id
        self.promised_id = None
        self.accepted_id = None
        self.accepted_value = None
        self.log = []
        self._lock = threading.Lock()

    def handle_prepare(self, message):
        proposal_id = message.proposal_id
        with self._lock:
            logger.debug(f"Acceptor {self.id}: Prepare received, proposal_id={proposal_id}, promised_id={self.promised_id}")
            self.log.append({
                "action": "receive_prepare",
                "proposal_id": proposal_id,
                "promised_id": self.promised_id
            })

            if self.promised_id is None or proposal_id > self.promised_id:
                self.promised_id = proposal_id
                logger.info(f"Acceptor {self.id}: Promised proposal_id={proposal_id}")
                response = Message.create_promise(
                    proposal_id=proposal_id,
                    acceptor_id=self.id,
                    accepted_id=self.accepted_id,
                    accepted_value=self.accepted_value
                )
                self.log.append({
                    "action": "send_promise",
                    "proposal_id": proposal_id,
                    "accepted_id": self.accepted_id,
                    "accepted_value": self.accepted_value
                })
                return response
            else:
                logger.warning(f"Acceptor {self.id}: Rejecting prepare proposal_id={proposal_id}, already promised_id={self.promised_id}")
                response = Message.create_reject(proposal_id, self.id, f"已承诺更高编号 {self.promised_id}")
                self.log.append({
                    "action": "reject_prepare",
                    "proposal_id": proposal_id,
                    "reason": f"已承诺更高编号 {self.promised_id}"
                })
                return response

    def handle_accept(self, message):
        proposal_id = message.proposal_id
        value = message.value
        with self._lock:
            logger.debug(f"Acceptor {self.id}: Accept received, proposal_id={proposal_id}, value={value}, promised_id={self.promised_id}")

            self.log.append({
                "action": "receive_accept",
                "proposal_id": proposal_id,
                "value": value,
                "promised_id": self.promised_id
            })

            if self.promised_id is None or proposal_id >= self.promised_id:
                self.promised_id = proposal_id
                self.accepted_id = proposal_id
                self.accepted_value = value
                logger.info(f"Acceptor {self.id}: Accepted proposal_id={proposal_id}, value={value}")
                response = Message.create_accepted(proposal_id, value, self.id)
                self.log.append({
                    "action": "send_accepted",
                    "proposal_id": proposal_id,
                    "value": value
                })
                return response
            else:
                logger.warning(f"Acceptor {self.id}: Rejecting accept proposal_id={proposal_id}, already promised_id={self.promised_id}")
                response = Message.create_reject(proposal_id, self.id, f"已承诺更高编号 {self.promised_id}")
                self.log.append({
                    "action": "reject_accept",
                    "proposal_id": proposal_id,
                    "reason": f"已承诺更高编号 {self.promised_id}"
                })
                return response

    def reset(self):
        with self._lock:
            self.promised_id = None
            self.accepted_id = None
            self.accepted_value = None
            self.log = []
