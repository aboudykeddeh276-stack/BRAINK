from __future__ import annotations
class SectorRuntime:
    def __init__(self, manifest, hr, braink):
        self.manifest=manifest; self.hr=hr; self.braink=braink
    def execute(self,function,payload,work_class="normal"):
        if function not in self.manifest["market_functions"]:
            return {"status":"FUNCTION_NOT_REGISTERED","function":function}
        assignment=self.hr.assign(self.manifest["sector_id"],function,work_class)
        if assignment["status"]!="ASSIGNED": return assignment
        route=self.braink.route(self.manifest["sector_id"],function,payload)
        return {"status":"DISPATCHED","assignment":assignment,"route":route}
