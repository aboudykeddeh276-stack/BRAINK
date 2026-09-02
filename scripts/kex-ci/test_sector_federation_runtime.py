from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.sector_federation_runtime import SectorFederationRuntime,FederationTask

assignments={
 "agent://research/a":{"sector":"research_learning_evolution","capabilities":{"research.discover"},"scope":"KEX://RESEARCH/","root":"a"*64},
 "agent://runtime/a":{"sector":"runtime_servers","capabilities":{"runtime.inspect"},"scope":"KEX://RUNTIME/","root":"b"*64},
}
def hr(agent,sector,capability,target):
    a=assignments.get(agent)
    if not a:return {"authorized":False,"reason":"AGENT_UNASSIGNED"}
    if a["sector"]!=sector:return {"authorized":False,"reason":"SECTOR_MISMATCH"}
    if capability not in a["capabilities"]:return {"authorized":False,"reason":"CAPABILITY_UNASSIGNED"}
    if not target.startswith(a["scope"]):return {"authorized":False,"reason":"TARGET_OUT_OF_SCOPE"}
    return {"authorized":True,"assignment_root":a["root"]}

fed=SectorFederationRuntime(hr)
fed.bind_sector("research_learning_evolution",lambda t:{"status":"EXECUTED","finding_root":"c"*64,"work_module":t.work_module})

ok=fed.dispatch(FederationTask("T1","research_learning_evolution","workmodule://research/discover","research.discover","DISCOVER",{},"agent://research/a","KEX://RESEARCH/BRAINK"))
assert ok.status=="EXECUTED"

wrong=fed.dispatch(FederationTask("T2","runtime_servers","workmodule://runtime/inspect","runtime.inspect","INSPECT",{},"agent://research/a","KEX://RUNTIME/HOST"))
assert wrong.status=="REJECTED_HR_AUTHORITY"

hole=fed.dispatch(FederationTask("T3","runtime_servers","workmodule://runtime/inspect","runtime.inspect","INSPECT",{},"agent://runtime/a","KEX://RUNTIME/HOST"))
assert hole.status=="DEFERRED_SECTOR_HOLE"
assert fed.state_root
print("SECTOR_FEDERATION_RUNTIME_PASS")
