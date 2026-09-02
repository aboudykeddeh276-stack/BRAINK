from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Usage:
    tenant_id:str
    service_id:str
    unit:str
    quantity:float
    cost_minor:int

class UsageMeter:
    def __init__(self): self.events=[]
    def record(self,tenant_id,service_id,unit,quantity,cost_minor=0):
        if quantity < 0 or cost_minor < 0: raise ValueError("negative usage/cost")
        e=Usage(tenant_id,service_id,unit,float(quantity),int(cost_minor))
        self.events.append(e); return e
    def totals(self,tenant_id):
        ev=[e for e in self.events if e.tenant_id==tenant_id]
        return {"tenant_id":tenant_id,"units":sum(e.quantity for e in ev),"cost_minor":sum(e.cost_minor for e in ev)}
