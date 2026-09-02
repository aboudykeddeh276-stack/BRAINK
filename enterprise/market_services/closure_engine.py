from __future__ import annotations
from .capability_registry import CapabilityRegistry
GROUPS=("research","runtime","verification","evolution","proof")

class CapabilityClosureEngine:
    def __init__(self,registry:CapabilityRegistry): self.registry=registry
    def work_queue(self):
        out=[]
        for o in self.registry.open_obligations():
            out.append({**o,
              "instruction":f"Research, implement, test, qualify and bind adapter '{o['adapter_id']}' required by {o['sector']}::{o['function']}.",
              "groups":[{"group":g,"supervisor":f"supervisor://capability/{o['adapter_id']}/{g}","worker":f"agent://capability/{o['adapter_id']}/{g}","work_module_id":o["work_module_id"]} for g in GROUPS]})
        return out
    def summary(self):
        q=self.work_queue();return {"open_obligations":len(q),"distinct_adapters":len({x['adapter_id'] for x in q}),"distinct_sector_functions":len({(x['sector'],x['function']) for x in q})}
