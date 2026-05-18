from services.consensus.message import Message, MessageType
import time
import uuid

class Proposer:
    def __init__(self, proposer_id=None):
        self.id = proposer_id or f"proposer-{uuid.uuid4().hex[:6]}"
        self.proposal_counter = 0
        self.current_proposal_id = 0
        self.current_value = None
        self.promises_received = []
        self.accepts_received = []
        self.log = []
    
    def generate_proposal_id(self):
        self.proposal_counter += 1
        # Combine timestamp (ms) with counter for global uniqueness
        self.current_proposal_id = int(time.time() * 1000) * 1000 + self.proposal_counter
        return self.current_proposal_id
    
    def propose(self, value):
        self.current_value = value
        proposal_id = self.generate_proposal_id()
        self.promises_received = []
        self.accepts_received = []
        
        self.log.append({
            "action": "start_propose",
            "proposal_id": proposal_id,
            "value": value
        })
        
        return Message.create_prepare(proposal_id, sender=self.id)
    
    def handle_promise(self, message):
        if message.proposal_id != self.current_proposal_id:
            return None
        
        self.promises_received.append({
            "acceptor_id": message.acceptor_id,
            "accepted_id": message.accepted_id,
            "accepted_value": message.accepted_value
        })
        
        self.log.append({
            "action": "receive_promise",
            "acceptor_id": message.acceptor_id,
            "total_promises": len(self.promises_received)
        })
        
        return len(self.promises_received)
    
    def has_majority(self, total_acceptors):
        majority = (total_acceptors // 2) + 1
        return len(self.promises_received) >= majority
    
    def get_accept_value(self):
        latest_accepted = None
        latest_id = 0
        
        for promise in self.promises_received:
            if promise["accepted_id"] and promise["accepted_id"] > latest_id:
                latest_id = promise["accepted_id"]
                latest_accepted = promise["accepted_value"]
        
        if latest_accepted:
            return latest_accepted
        return self.current_value
    
    def create_accept_message(self):
        value = self.get_accept_value()
        self.log.append({
            "action": "send_accept",
            "proposal_id": self.current_proposal_id,
            "value": value
        })
        return Message.create_accept(self.current_proposal_id, value, sender=self.id)
    
    def handle_accepted(self, message):
        if message.proposal_id != self.current_proposal_id:
            return None
        
        self.accepts_received.append({
            "acceptor_id": message.acceptor_id,
            "value": message.value
        })
        
        self.log.append({
            "action": "receive_accepted",
            "acceptor_id": message.acceptor_id,
            "total_accepts": len(self.accepts_received)
        })
        
        return len(self.accepts_received)
    
    def has_accept_majority(self, total_acceptors):
        majority = (total_acceptors // 2) + 1
        return len(self.accepts_received) >= majority
    
    def get_final_value(self):
        if self.accepts_received:
            return self.accepts_received[0]["value"]
        return None
    
    def reset(self):
        self.current_proposal_id = 0
        self.current_value = None
        self.promises_received = []
        self.accepts_received = []
        self.log = []
