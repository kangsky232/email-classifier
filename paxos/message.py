from enum import Enum
import uuid
import time

class MessageType(Enum):
    PREPARE = "prepare"
    PROMISE = "promise"
    ACCEPT = "accept"
    ACCEPTED = "accepted"
    REJECT = "reject"
    LEARN = "learn"

class Message:
    def __init__(self, msg_type, proposal_id, value=None, sender=None, acceptor_id=None, accepted_id=None, accepted_value=None):
        self.id = str(uuid.uuid4())[:8]
        self.type = msg_type
        self.proposal_id = proposal_id
        self.value = value
        self.sender = sender
        self.acceptor_id = acceptor_id
        self.accepted_id = accepted_id
        self.accepted_value = accepted_value
        self.timestamp = time.time()
    
    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "proposal_id": self.proposal_id,
            "value": self.value,
            "sender": self.sender,
            "acceptor_id": self.acceptor_id,
            "accepted_id": self.accepted_id,
            "accepted_value": self.accepted_value,
            "timestamp": self.timestamp
        }
    
    @staticmethod
    def create_prepare(proposal_id, sender=None):
        return Message(MessageType.PREPARE, proposal_id, sender=sender)
    
    @staticmethod
    def create_promise(proposal_id, acceptor_id, accepted_id=None, accepted_value=None):
        return Message(MessageType.PROMISE, proposal_id, acceptor_id=acceptor_id, accepted_id=accepted_id, accepted_value=accepted_value)
    
    @staticmethod
    def create_accept(proposal_id, value, sender=None):
        return Message(MessageType.ACCEPT, proposal_id, value=value, sender=sender)
    
    @staticmethod
    def create_accepted(proposal_id, value, acceptor_id):
        return Message(MessageType.ACCEPTED, proposal_id, value=value, acceptor_id=acceptor_id)
    
    @staticmethod
    def create_reject(proposal_id, acceptor_id, reason=None):
        return Message(MessageType.REJECT, proposal_id, acceptor_id=acceptor_id, value=reason)
    
    @staticmethod
    def create_learn(value):
        return Message(MessageType.LEARN, 0, value=value)
