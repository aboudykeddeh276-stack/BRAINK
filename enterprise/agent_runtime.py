from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Callable,Dict,Mapping

@dataclass(frozen=True)
class AgentHandler:
    agent_id:str; capability:str; fn:Callable[[Mapping[str,Any]],Mapping[str,Any]]

class AgentRuntime:
    def __init__(self): self.handlers:Dict[str,AgentHandler]={}
    def bind(self,address,agent_id,capability,fn): self.handlers[address]=AgentHandler(agent_id,capability,fn)
    def invoke(self,address,capability,payload):
        h=self.handlers.get(address)
        if h is None:return {"status":"HOLE","reason":"AGENT_UNBOUND"}
        if h.capability!=capability:return {"status":"HOLE","reason":"CAPABILITY_MISMATCH"}
        return {"status":"EXECUTED","agent_id":h.agent_id,"effect":dict(h.fn(payload))}
