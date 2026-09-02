from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import FrozenSet, Dict
import time, uuid

@dataclass(frozen=True)
class Role:
    role_id:str
    sector_id:str
    capabilities:FrozenSet[str]
    approval_classes:FrozenSet[str]

@dataclass
class Worker:
    worker_id:str
    worker_type:str
    sector_id:str
    roles:FrozenSet[str]
    capacity:int=100
    allocated:int=0

@dataclass(frozen=True)
class Assignment:
    assignment_id:str
    sector_id:str
    function:str
    worker_id:str
    work_class:str
    approval_required:bool
    created_ns:int

class HRFabric:
    def __init__(self):
        self.roles:Dict[str,Role]={}
        self.workers:Dict[str,Worker]={}
        self.assignments=[]
    def register_role(self,role): self.roles[role.role_id]=role
    def register_worker(self,worker): self.workers[worker.worker_id]=worker
    def assign(self,sector_id,function,work_class="normal"):
        candidates=[]
        for w in self.workers.values():
            if w.sector_id not in {sector_id,"SHARED"}: continue
            caps=set()
            for rid in w.roles:
                r=self.roles.get(rid)
                if r: caps.update(r.capabilities)
            if function in caps and w.allocated < w.capacity:
                candidates.append((w.allocated,w.worker_id,w))
        if not candidates:
            return {"status":"UNSTAFFED","sector_id":sector_id,"function":function}
        _,_,worker=sorted(candidates,key=lambda x:(x[0],x[1]))[0]
        worker.allocated+=1
        approval_required=work_class in {"privileged","external","financial","regulated"}
        a=Assignment("ASN-"+uuid.uuid4().hex[:12],sector_id,function,worker.worker_id,work_class,approval_required,time.time_ns())
        self.assignments.append(a)
        return {"status":"ASSIGNED","assignment":asdict(a)}
