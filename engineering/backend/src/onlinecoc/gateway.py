from typing import Protocol

class ApplicationGateway(Protocol):
    def command(self, account: str, message: dict) -> dict: ...
    def project(self, account: str) -> dict: ...
    def receipt(self, account: str, command_id: str) -> dict: ...
    def notifications(self, account: str, after=0, limit=50) -> dict: ...

    def chat_members(self, account: str) -> list: ...
    def chat_history(self, account: str, channel_id: str, before=None, limit=50) -> dict: ...

class InProcessTransport:
    def __init__(self, gateway: ApplicationGateway, account: str):
        self.gateway, self.account = gateway, account
    def command(self, message):return self.gateway.command(self.account,message)
    def snapshot(self):return self.gateway.project(self.account)
    def receipt(self, command_id):return self.gateway.receipt(self.account,command_id)
    def notifications(self, after=0, limit=50):return self.gateway.notifications(self.account,after,limit)
    def chat_history(self, channel_id, before=None, limit=50):return self.gateway.chat_history(self.account,channel_id,before,limit)
    def chat_members(self):return self.gateway.chat_members(self.account)
    def knowledge_capabilities(self):return self.gateway.knowledge.capabilities(self.account)
    def knowledge_search(self,args):return self.gateway.knowledge.search(self.account,args)
    def knowledge_read(self,args):return self.gateway.knowledge.read(self.account,args)
    def knowledge_preview(self,args):return self.gateway.knowledge.preview(self.account,args)
    def knowledge_grants(self,args):return self.gateway.knowledge.grants(self.account,args)
