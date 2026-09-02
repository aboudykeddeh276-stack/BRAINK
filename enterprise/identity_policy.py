from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet

@dataclass(frozen=True)
class Principal:
    principal_id:str
    principal_type:str  # user|agent|service|workload
    tenant_id:str
    roles:FrozenSet[str]

@dataclass(frozen=True)
class Tool:
    tool_id:str
    action_class:str  # read|draft|write|privileged|external
    scopes:FrozenSet[str]

@dataclass(frozen=True)
class Decision:
    allowed:bool
    requires_approval:bool
    reason:str

class PolicyEngine:
    HIGH_RISK={"write","privileged","external"}
    def decide(self,principal:Principal,tool:Tool,resource_tenant:str,approved:bool=False)->Decision:
        if principal.tenant_id != resource_tenant:
            return Decision(False,False,"CROSS_TENANT_DENIED")
        if not tool.scopes.intersection(principal.roles):
            return Decision(False,False,"NO_AUTHORIZED_SCOPE")
        if tool.action_class in self.HIGH_RISK and not approved:
            return Decision(False,True,"APPROVAL_REQUIRED")
        return Decision(True,False,"ALLOW")
