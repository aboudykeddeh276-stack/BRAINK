from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict
import time

@dataclass(frozen=True)
class Arbitration:
    decision:str
    reason:str
    mutation_class:str | None
    subject:str
    target:str
    created_ns:int

class MutationArbiter:
    def __init__(self, evolution_fabric, binder, observer_policy):
        self.evolution=evolution_fabric
        self.binder=binder
        self.policy=observer_policy
        self.history=[]
    def arbitrate(self, subject_id:str, target_address:str, payload:Dict[str,Any], signals=None)->Arbitration:
        signals=list(signals or [])
        decisions=[self.policy.decide(s) for s in signals]
        if any(d.action=="QUARANTINE_AND_REPAIR" for d in decisions):
            a=Arbitration("QUARANTINE","critical observer contradiction",None,subject_id,target_address,time.time_ns())
        elif any(d.action=="DEFER_AND_RESOLVE" for d in decisions):
            a=Arbitration("DEFER","unresolved address/adapter",None,subject_id,target_address,time.time_ns())
        else:
            mc=self.evolution.classify(subject_id,target_address,payload,"arbiter")
            a=Arbitration("DISPATCH","structural classification accepted",mc.value,subject_id,target_address,time.time_ns())
        self.history.append(a)
        return a
    def dispatch(self, subject_id, target_address, payload, signals=None):
        a=self.arbitrate(subject_id,target_address,payload,signals)
        if a.decision!="DISPATCH":
            return {"status":a.decision,"arbitration":asdict(a)}
        out=self.evolution.dispatch(subject_id,target_address,payload,"mutation-arbiter")
        return {"status":"DISPATCHED","arbitration":asdict(a),"result":out}
