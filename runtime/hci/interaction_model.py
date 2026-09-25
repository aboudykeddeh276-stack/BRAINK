from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

class InteractionViolation(RuntimeError):
    pass

class Surface(str, Enum):
    HOME='HOME'; WORK='WORK'; FILES='FILES'; TASKS='TASKS'; ADMIN='ADMIN'; DIAGNOSTICS='DIAGNOSTICS'
class ActionClass(str, Enum):
    USER='USER'; ADMIN='ADMIN'; MAINTENANCE='MAINTENANCE'
class Visibility(str, Enum):
    PRIMARY='PRIMARY'; SECONDARY='SECONDARY'; HIDDEN='HIDDEN'

@dataclass(frozen=True)
class InteractionAction:
    action_id:str; label:str; intent:str; action_class:ActionClass; surface:Surface; visibility:Visibility; capability:str
    destructive:bool=False; confirmation_required:bool=False

@dataclass(frozen=True)
class MCPBinding:
    action_id:str; mcp_primitive:str; mcp_name:str; authority_scope:str; proof_required:bool; user_visible:bool

@dataclass(frozen=True)
class StatusStrip:
    overall:str; ai:str; tasks:str; files:str; sync:str; attention_count:int; diagnostic_state:str

def canonical(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()
def digest(value:Any)->str:
    return sha256(canonical(value)).hexdigest()

class InteractionRegistry:
    def __init__(self,actions:Iterable[InteractionAction],bindings:Iterable[MCPBinding])->None:
        self.actions={a.action_id:a for a in actions}; self.bindings={b.action_id:b for b in bindings}
        if set(self.bindings)-set(self.actions): raise InteractionViolation('BINDING_WITHOUT_ACTION')
        for action in self.actions.values(): self._validate(action)
    def _validate(self,action:InteractionAction)->None:
        if action.action_class==ActionClass.MAINTENANCE and action.visibility==Visibility.PRIMARY:
            raise InteractionViolation('MAINTENANCE_CANNOT_BE_PRIMARY')
        if action.action_class==ActionClass.ADMIN and action.surface==Surface.HOME and action.visibility==Visibility.PRIMARY:
            raise InteractionViolation('ADMIN_CANNOT_BE_PRIMARY_HOME_ACTION')
        if action.destructive and not action.confirmation_required:
            raise InteractionViolation('DESTRUCTIVE_ACTION_REQUIRES_CONFIRMATION')
        binding=self.bindings.get(action.action_id)
        if binding and action.action_class!=ActionClass.USER and binding.user_visible:
            raise InteractionViolation('PRIVILEGED_MCP_BINDING_CANNOT_BE_DIRECT_USER_CONTROL')
    def primary_home_actions(self):
        return tuple(sorted((a for a in self.actions.values() if a.surface==Surface.HOME and a.action_class==ActionClass.USER and a.visibility==Visibility.PRIMARY),key=lambda a:a.action_id))
    def diagnostics_actions(self):
        return tuple(sorted((a for a in self.actions.values() if a.surface in {Surface.ADMIN,Surface.DIAGNOSTICS} or a.action_class in {ActionClass.ADMIN,ActionClass.MAINTENANCE}),key=lambda a:a.action_id))
    def resolve(self,action_id:str,*,actor_scope:str)->MCPBinding:
        action=self.actions.get(action_id)
        if action is None: raise InteractionViolation('ACTION_UNKNOWN')
        binding=self.bindings.get(action_id)
        if binding is None: raise InteractionViolation('ACTION_UNBOUND')
        if action.action_class!=ActionClass.USER and actor_scope not in {'ADMIN','INFRA'}:
            raise InteractionViolation('PRIVILEGED_ACTION_SCOPE_REQUIRED')
        return binding

def default_registry()->InteractionRegistry:
    actions=(
        InteractionAction('ai.ask','Ask BRAINK','ai.interact',ActionClass.USER,Surface.HOME,Visibility.PRIMARY,'chat.execute'),
        InteractionAction('task.new','New task','task.create',ActionClass.USER,Surface.HOME,Visibility.PRIMARY,'tasks.create'),
        InteractionAction('task.open','Open tasks','task.browse',ActionClass.USER,Surface.HOME,Visibility.PRIMARY,'tasks.list'),
        InteractionAction('file.open','Browse files','file.browse',ActionClass.USER,Surface.HOME,Visibility.PRIMARY,'files.list'),
        InteractionAction('file.recent','Recent files','file.recent',ActionClass.USER,Surface.HOME,Visibility.SECONDARY,'files.recent'),
        InteractionAction('system.health','System health','system.health',ActionClass.USER,Surface.HOME,Visibility.SECONDARY,'health.summary'),
        InteractionAction('diag.open','Diagnostics','diagnostics.open',ActionClass.MAINTENANCE,Surface.DIAGNOSTICS,Visibility.SECONDARY,'diagnostics.summary'),
        InteractionAction('diag.hosts','Host diagnostics','diagnostics.hosts',ActionClass.MAINTENANCE,Surface.DIAGNOSTICS,Visibility.HIDDEN,'host.inspect'),
        InteractionAction('diag.mesh','Network diagnostics','diagnostics.mesh',ActionClass.MAINTENANCE,Surface.DIAGNOSTICS,Visibility.HIDDEN,'mesh.inspect'),
        InteractionAction('admin.runtime','Runtime administration','admin.runtime',ActionClass.ADMIN,Surface.ADMIN,Visibility.HIDDEN,'runtime.control'),
        InteractionAction('admin.service.restart','Restart service','admin.service.restart',ActionClass.ADMIN,Surface.ADMIN,Visibility.HIDDEN,'service.restart',True,True),
    )
    bindings=(
        MCPBinding('ai.ask','tool','braink.chat.execute','USER',True,True),
        MCPBinding('task.new','tool','braink.tasks.create','USER',True,True),
        MCPBinding('task.open','resource','braink://tasks','USER',False,True),
        MCPBinding('file.open','resource','braink://files','USER',False,True),
        MCPBinding('file.recent','resource','braink://files/recent','USER',False,True),
        MCPBinding('system.health','resource','braink://health/summary','USER',False,True),
        MCPBinding('diag.open','resource','braink://diagnostics','ADMIN',False,False),
        MCPBinding('diag.hosts','tool','braink.host.inspect','ADMIN',True,False),
        MCPBinding('diag.mesh','tool','braink.mesh.inspect','ADMIN',True,False),
        MCPBinding('admin.runtime','tool','braink.runtime.control','ADMIN',True,False),
        MCPBinding('admin.service.restart','tool','braink.service.restart','ADMIN',True,False),
    )
    return InteractionRegistry(actions,bindings)

def home_dashboard(*,ai_state:str,task_summary:Mapping[str,Any],recent_files:list[Mapping[str,Any]],system_summary:Mapping[str,Any])->dict[str,Any]:
    registry=default_registry(); attention=int(task_summary.get('attention_count',0) or 0); degraded=bool(system_summary.get('degraded',False))
    strip=StatusStrip('ATTENTION' if attention or degraded else 'READY',ai_state,str(task_summary.get('status','READY')),'READY',str(system_summary.get('sync','UNKNOWN')),attention,'AVAILABLE' if system_summary.get('diagnostics_available',True) else 'UNAVAILABLE')
    body={'schema':'braink.user-home.v1','principle':'USER_GOALS_FIRST_SYSTEM_MAINTENANCE_AUTOMATED','primary_actions':[asdict(a) for a in registry.primary_home_actions()],'ai':{'state':ai_state,'entry_action':'ai.ask'},'tasks':dict(task_summary),'files':{'recent':recent_files[:8],'browse_action':'file.open'},'status_strip':asdict(strip),'diagnostics':{'surface':'DIAGNOSTICS','action':'diag.open','expanded':False}}
    body['state_root']=digest(body); return body
