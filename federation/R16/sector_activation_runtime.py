from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any
import hashlib, json, time, uuid

def sha(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class WorkReceipt:
    work_id:str
    sector_id:str
    function:str
    runtime_address:str
    hr_team:str
    server_sets:tuple[str,...]
    repository_route:str
    status:str
    payload_root:str
    created_ns:int

class SectorActivationRuntime:
    """Generic activation layer over R15/R16. Bindings are data; sector implementations are not cloned."""
    def __init__(self, activation:Dict[str,Any]):
        self.activation=activation
        self.bindings={b["sector_id"]:b for b in activation["bindings"]}
        self.receipts=[]
        self.handlers={}
    def register_server_handler(self, server_set:str, fn):
        self.handlers[server_set]=fn
    def resolve(self, sector_id:str, function:str):
        b=self.bindings.get(sector_id)
        if not b: return {"status":"UNKNOWN_SECTOR"}
        if function not in b["market_functions"]:
            return {"status":"FUNCTION_NOT_REGISTERED","sector_id":sector_id,"function":function}
        return {"status":"RESOLVED","binding":b}
    def execute(self, sector_id:str, function:str, payload:Dict[str,Any], work_class:str="normal"):
        resolved=self.resolve(sector_id,function)
        if resolved["status"]!="RESOLVED": return resolved
        b=resolved["binding"]
        server_results=[]
        for server_set in b["server_sets"]:
            fn=self.handlers.get(server_set)
            if fn is None:
                server_results.append({"server_set":server_set,"status":"BOUND_NO_HANDLER"})
            else:
                out=fn({"sector_id":sector_id,"function":function,"payload":payload,"work_class":work_class})
                server_results.append({"server_set":server_set,**out})
        status="DISPATCHED" if all(r["status"] in {"DISPATCHED","BOUND_NO_HANDLER","ACCEPTED"} for r in server_results) else "PARTIAL"
        repository_route=b.get("repository_owners",{}).get("federation","aboudykeddeh276-stack/BRAINK")
        wr=WorkReceipt("WORK-"+uuid.uuid4().hex[:12],sector_id,function,b["runtime_address"],b["hr_team"],tuple(b["server_sets"]),repository_route,status,sha(payload),time.time_ns())
        self.receipts.append(wr)
        return {"status":status,"work":asdict(wr),"server_results":server_results}
    def activation_summary(self):
        return {"sector_count":len(self.bindings),"active_bindings":sum(1 for b in self.bindings.values() if b["activation_state"]=="BOUND_READY"),"work_receipts":len(self.receipts),"receipt_root":sha([asdict(r) for r in self.receipts])}
