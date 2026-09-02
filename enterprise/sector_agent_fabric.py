from __future__ import annotations
from .sector_runtime import SectorRuntime,SectorWorkModule

GROUPS=("research","runtime","verification","evolution","proof")

class SectorAgentFabric:
    """Expands a sector function into the same five work groups and recursively supervises them."""
    def __init__(self,runtime:SectorRuntime):
        self.runtime=runtime

    def deploy_module(self,module:SectorWorkModule,sector_supervisor:str):
        edges=[]
        for group in GROUPS:
            group_supervisor=f"supervisor://{module.sector.lower()}/{group}/{module.module_id}"
            edges.append(self.runtime.supervise(sector_supervisor,group_supervisor,module,f"{group}:supervision"))
            worker=f"agent://{module.sector.lower()}/{group}/{module.module_id}"
            edges.append(self.runtime.supervise(group_supervisor,worker,module,f"{group}:execution"))
        return edges

    def deploy_sector(self,sector:str):
        supervisor=f"supervisor://sector/{sector.lower()}"
        modules=self.runtime.work_modules(sector)
        return {"sector":sector,"supervisor":supervisor,"modules":modules,
                "edges":[e for m in modules for e in self.deploy_module(m,supervisor)]}
