from __future__ import annotations
from typing import Any,Dict

from enterprise.sector_runtime import SectorRuntime
from enterprise.hr_fabric import HRFabric, Role, Worker
from enterprise.braink_sector_federation import BrainKSectorFederation

class SectorEnterpriseFederation:
    """Unifies recursive sector supervision, HR staffing/accountability, and BRAINK state/routing/evidence."""
    def __init__(self,registry:Dict[str,Any]):
        self.registry=registry
        self.supervisors=SectorRuntime(registry)
        self.hr=HRFabric()
        self.braink=BrainKSectorFederation()

    def bootstrap_sector(self,sector_id:str,manifest:Dict[str,Any]):
        self.braink.register(manifest)
        role_id=f"role://{sector_id.lower()}/operator"
        functions=frozenset(manifest["market_functions"])
        self.hr.register_role(Role(role_id,sector_id,functions,frozenset()))
        self.hr.register_worker(Worker(f"worker://{sector_id.lower()}/agent","agent",sector_id,frozenset({role_id}),100,0))
        return {"status":"BOOTSTRAPPED","sector_id":sector_id,"runtime_address":manifest["braink"]["runtime_address"]}

    def dispatch(self,sector_id:str,function:str,payload:Dict[str,Any],work_class:str="normal"):
        manifest=self.registry["repository_manifests"][sector_id]
        if function not in manifest["market_functions"]:
            return {"status":"FUNCTION_NOT_REGISTERED","sector_id":sector_id,"function":function}
        assignment=self.hr.assign(sector_id,function,work_class)
        if assignment["status"]!="ASSIGNED":
            return assignment
        route=self.braink.route(sector_id,function,payload)
        return {"status":"DISPATCHED","assignment":assignment,"route":route}
