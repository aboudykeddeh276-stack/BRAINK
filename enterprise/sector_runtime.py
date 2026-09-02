from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Dict,List,Optional
import hashlib,json,time,uuid

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True)
class SectorWorkModule:
    module_id:str
    sector:str
    function:str
    instruction:str
    acceptance:tuple[str,...]
    control_requirements:tuple[str,...]
    adapter_requirements:tuple[str,...]
    predecessor_root:Optional[str]

@dataclass(frozen=True)
class SupervisorEdge:
    edge_id:str
    supervisor_id:str
    child_id:str
    scope:str
    epoch:int
    work_module_id:str
    created_ns:int

class SectorRuntime:
    """One recursive supervisor runtime for all sectors. Sector policy is data, not subclass sprawl."""
    def __init__(self,registry:Dict[str,Any]):
        self.registry=registry
        self.edges:Dict[str,SupervisorEdge]={}
        self.receipts:List[Dict[str,Any]]=[]
        self.epoch=0

    def work_modules(self,sector:str)->List[SectorWorkModule]:
        cfg=self.registry["sectors"][sector]
        out=[]
        for fn in cfg["market_functions"]:
            body={"sector":sector,"function":fn,"controls":cfg["controls"],"adapters":cfg["required_adapters"]}
            out.append(SectorWorkModule(
                module_id=f"WM-{sector}-{root(body)[:12]}",
                sector=sector,function=fn,
                instruction=f"Research, qualify, implement, test, reconcile and evolve the {fn} function for {sector}.",
                acceptance=("function contract defined","adapter state explicit","controls mapped","tests defined","receipt emitted"),
                control_requirements=tuple(cfg["controls"]),
                adapter_requirements=tuple(cfg["required_adapters"]),
                predecessor_root=None))
        return out

    def supervise(self,supervisor_id:str,child_id:str,module:SectorWorkModule,scope:str)->SupervisorEdge:
        self.epoch+=1
        edge=SupervisorEdge("SUP-"+uuid.uuid4().hex[:12],supervisor_id,child_id,scope,self.epoch,module.module_id,time.time_ns())
        self.edges[edge.edge_id]=edge
        return edge

    def complete(self,edge:SupervisorEdge,status:str,evidence:Dict[str,Any]):
        receipt={"edge_id":edge.edge_id,"work_module_id":edge.work_module_id,"status":status,
                 "evidence_root":root(evidence),"completed_ns":time.time_ns()}
        self.receipts.append(receipt)
        return receipt

    def collapse_subtree(self,supervisor_id:str):
        children=[e for e in self.edges.values() if e.supervisor_id==supervisor_id]
        roots=[r["evidence_root"] for r in self.receipts if r["edge_id"] in {e.edge_id for e in children}]
        return {"supervisor_id":supervisor_id,"child_count":len(children),"receipt_root":root(sorted(roots))}
