from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Dict,Any
import hashlib,json,time,uuid

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

@dataclass
class FoundryInstance:
    instance_id:str
    foundry_id:str
    runtime_address:str
    state:str
    service_count:int
    process_count:int
    domain_count:int
    created_ns:int

class FoundryMeshRuntime:
    def __init__(self,register:Dict[str,Any]):
        self.register=register; self.instances={}; self.edges=[]; self.events=[]
    def instantiate(self,foundry_id):
        f=self.register["foundries"][foundry_id]
        iid="FOUNDRY-"+uuid.uuid4().hex[:12]
        inst=FoundryInstance(iid,foundry_id,f"runtime://keddeh/foundry/{foundry_id.lower()}","ACTIVE",len(f["services"]),len(f["processes"]),len(f["domains"]),time.time_ns())
        self.instances[foundry_id]=inst; self.emit(foundry_id,"INSTANTIATE",asdict(inst)); return asdict(inst)
    def bind(self,source,target,relation):
        if source not in self.instances or target not in self.instances: return {"status":"UNINSTANTIATED"}
        edge={"source":source,"target":target,"relation":relation,"edge_root":root([source,target,relation])}
        self.edges.append(edge); self.emit(source,"BIND",edge); return {"status":"BOUND","edge":edge}
    def emit(self,foundry_id,kind,payload):
        e={"foundry_id":foundry_id,"kind":kind,"payload_root":root(payload),"created_ns":time.time_ns()}; e["event_root"]=root(e); self.events.append(e); return e
    def summary(self):
        return {"foundries":len(self.instances),"services":sum(i.service_count for i in self.instances.values()),"processes":sum(i.process_count for i in self.instances.values()),"domains":sum(i.domain_count for i in self.instances.values()),"edges":len(self.edges),"event_root":root(self.events)}
