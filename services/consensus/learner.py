from services.consensus.message import Message, MessageType
import logging

logger = logging.getLogger(__name__)

class Learner:
    def __init__(self, learner_id):
        self.id = learner_id
        self.learned_values = {}
        self.log = []
    
    def learn(self, message):
        value = message.value
        proposal_id = message.proposal_id

        logger.info(f"Learner {self.id}: Learned value={value} for proposal_id={proposal_id}")
        self.learned_values[proposal_id] = value
        
        self.log.append({
            "action": "learn",
            "proposal_id": proposal_id,
            "value": value
        })
        
        return value
    
    def get_learned_value(self, proposal_id):
        return self.learned_values.get(proposal_id)
    
    def get_all_learned(self):
        return self.learned_values.copy()
    
    def reset(self):
        self.learned_values = {}
        self.log = []
