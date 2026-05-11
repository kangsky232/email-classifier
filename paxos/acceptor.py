from paxos.message import Message, MessageType

class Acceptor:
    def __init__(self, acceptor_id):
        self.id = acceptor_id
        self.promised_id = None
        self.accepted_id = None
        self.accepted_value = None
        self.log = []

    def handle_prepare(self, message):
        proposal_id = message.proposal_id
        self.log.append({
            "action": "receive_prepare",
            "proposal_id": proposal_id,
            "promised_id": self.promised_id
        })

        if self.promised_id is None or proposal_id > self.promised_id:
            self.promised_id = proposal_id
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
            response = Message.create_accepted(proposal_id, value, self.id)
            self.log.append({
                "action": "send_accepted",
                "proposal_id": proposal_id,
                "value": value
            })
            return response
        else:
            response = Message.create_reject(proposal_id, self.id, f"已承诺更高编号 {self.promised_id}")
            self.log.append({
                "action": "reject_accept",
                "proposal_id": proposal_id,
                "reason": f"已承诺更高编号 {self.promised_id}"
            })
            return response

    def reset(self):
        self.promised_id = None
        self.accepted_id = None
        self.accepted_value = None
        self.log = []
