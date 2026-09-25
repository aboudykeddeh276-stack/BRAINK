from __future__ import annotations
from typing import Any, Mapping
from .interaction_model import InteractionRegistry, InteractionViolation, default_registry
MCP_SPEC_VERSION='2026-07-28'
class MCPWorkflowRouter:
    def __init__(self,registry:InteractionRegistry|None=None)->None:self.registry=registry or default_registry()
    def capability_catalog(self,*,actor_scope:str='USER')->dict[str,Any]:
        entries=[]
        for action in self.registry.actions.values():
            try: binding=self.registry.resolve(action.action_id,actor_scope=actor_scope)
            except InteractionViolation: continue
            if actor_scope=='USER' and not binding.user_visible: continue
            entries.append({'action_id':action.action_id,'label':action.label,'intent':action.intent,'primitive':binding.mcp_primitive,'name':binding.mcp_name,'proof_required':binding.proof_required})
        return {'schema':'braink.mcp.workflow-catalog.v1','mcp_spec_version':MCP_SPEC_VERSION,'actor_scope':actor_scope,'entries':sorted(entries,key=lambda x:x['action_id'])}
    def dispatch_contract(self,action_id:str,payload:Mapping[str,Any],*,actor_scope:str='USER')->dict[str,Any]:
        binding=self.registry.resolve(action_id,actor_scope=actor_scope);action=self.registry.actions[action_id]
        return {'schema':'braink.mcp.dispatch-intent.v1','mcp_spec_version':MCP_SPEC_VERSION,'action_id':action_id,'user_intent':action.intent,'primitive':binding.mcp_primitive,'name':binding.mcp_name,'authority_scope':binding.authority_scope,'proof_required':binding.proof_required,'confirmation_required':action.confirmation_required,'payload':dict(payload)}
