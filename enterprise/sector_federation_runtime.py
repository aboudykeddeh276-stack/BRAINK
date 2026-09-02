from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Mapping
import hashlib, json, time

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class FederationTask:
    task_id:str; sector:str; work_module:str; capability:str; operation:str; payload:Mapping[str,Any]; agent_id:str; target:str
    @property
    def task_root(self): return root(asdict(self))

@dataclass(frozen=True)
class FederationReceipt:
    task_id:str; sector:str; agent_id:str; capability:str; status:str; hr_root:str; sector_receipt:Mapping[str,Any]; produced_at_ns:int
    @property
    def receipt_root(self): return root(asdict(self))

class SectorFederationRuntime:
    def __init__(self,hr_authorizer:Callable[...,Mapping[str,Any]]):
        self.hr_authorizer=hr_authorizer
        self.sectors:Dict[str,Callable[[FederationTask],Mapping[str,Any]]]={}
        self.receipts:list[FederationReceipt]=[]
    def bind_sector(self,sector:str,dispatcher:Callable[[FederationTask],Mapping[str,Any]]): self.sectors[sector]=dispatcher
    def dispatch(self,task:FederationTask):
        auth=self.hr_authorizer(task.agent_id,task.sector,task.capability,task.target)
        if not auth.get("authorized"):
            r=FederationReceipt(task.task_id,task.sector,task.agent_id,task.capability,"REJECTED_HR_AUTHORITY",auth.get("assignment_root",""),{"reason":auth.get("reason")},time.time_ns()); self.receipts.append(r); return r
        dispatcher=self.sectors.get(task.sector)
        if dispatcher is None:
            r=FederationReceipt(task.task_id,task.sector,task.agent_id,task.capability,"DEFERRED_SECTOR_HOLE",auth["assignment_root"],{"reason":"SECTOR_RUNTIME_UNBOUND"},time.time_ns()); self.receipts.append(r); return r
        effect=dict(dispatcher(task)); status=effect.get("status","EXECUTED")
        r=FederationReceipt(task.task_id,task.sector,task.agent_id,task.capability,status,auth["assignment_root"],effect,time.time_ns()); self.receipts.append(r); return r
    @property
    def state_root(self): return root([r.receipt_root for r in self.receipts])
