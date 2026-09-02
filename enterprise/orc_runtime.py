from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Iterable, Mapping, Optional
import hashlib, json, time

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class Obligation:
    obligation_id:str
    address:str
    capability:str
    operation:str
    payload:Mapping[str,Any]
    executable:bool=True
    dependency_ready:bool=True
    evidence_gap:float=0.0
    risk:float=0.0
    information_gain:float=0.0
    unlock_value:float=0.0
    effort:float=0.0

@dataclass(frozen=True)
class DispatchReceipt:
    obligation_id:str
    address:str
    status:str
    route:str
    effect:Mapping[str,Any]
    produced_at_ns:int
    predecessor_root:Optional[str]=None
    @property
    def receipt_root(self): return root(asdict(self))

class ORCRuntime:
    def __init__(self):
        self.routes:Dict[str,Callable[[Obligation],Mapping[str,Any]]]={}
        self.receipts:list[DispatchReceipt]=[]
    def register(self,address_prefix:str,handler:Callable[[Obligation],Mapping[str,Any]]):
        self.routes[address_prefix]=handler
    def select(self, obligations:Iterable[Obligation])->Optional[Obligation]:
        frontier=[o for o in obligations if o.executable and o.dependency_ready]
        if not frontier:return None
        def score(o): return 0.24*o.evidence_gap+0.22*o.risk+0.24*o.information_gain+0.20*o.unlock_value-0.18*o.effort
        return max(frontier,key=lambda o:(score(o),o.obligation_id))
    def _resolve(self,address:str):
        matches=[(p,h) for p,h in self.routes.items() if address.startswith(p)]
        return max(matches,key=lambda x:len(x[0])) if matches else None
    def dispatch(self,o:Obligation,predecessor_root:Optional[str]=None)->DispatchReceipt:
        resolved=self._resolve(o.address)
        if not resolved:
            effect={"state":"HOLE","reason":"NO_ROUTE","required_capability":o.capability}
            status="DEFERRED_HOLE"; route="HOLE"
        else:
            route,handler=resolved
            try:
                effect=dict(handler(o)); status=effect.get("status","EXECUTED")
            except Exception as exc:
                effect={"exception_type":type(exc).__name__,"reason":str(exc)}; status="REJECTED"
        r=DispatchReceipt(o.obligation_id,o.address,status,route,effect,time.time_ns(),predecessor_root)
        self.receipts.append(r); return r
