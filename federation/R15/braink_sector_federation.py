from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
import hashlib,json,time

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass
class SectorState:
    sector_id:str
    runtime_address:str
    state:str
    manifest_root:str
    last_event_root:str|None=None

class BrainKSectorFederation:
    def __init__(self):
        self.sectors:Dict[str,SectorState]={}
        self.events=[]
    def register(self,manifest):
        sid=manifest["sector_id"]
        s=SectorState(sid,manifest["braink"]["runtime_address"],"REGISTERED",root(manifest))
        self.sectors[sid]=s
        self.emit(sid,"REGISTER",{"manifest_root":s.manifest_root})
        return s
    def emit(self,sector_id,kind,payload):
        event={"sector_id":sector_id,"kind":kind,"payload":payload,"at_ns":time.time_ns()}
        event["event_root"]=root(event)
        self.events.append(event)
        if sector_id in self.sectors: self.sectors[sector_id].last_event_root=event["event_root"]
        return event
    def route(self,sector_id,function,payload):
        if sector_id not in self.sectors: return {"status":"UNKNOWN_SECTOR"}
        ev=self.emit(sector_id,"FUNCTION_ROUTE",{"function":function,"payload_root":root(payload)})
        return {"status":"ROUTED","runtime_address":self.sectors[sector_id].runtime_address,"event_root":ev["event_root"]}
    def reconcile(self,sector_id,signals):
        contradictions=[s for s in signals if s.get("severity") in {"HIGH","CRITICAL"}]
        state="RECONCILIATION_REQUIRED" if contradictions else "CONTINUE"
        self.sectors[sector_id].state=state
        self.emit(sector_id,"RECONCILE",{"state":state,"signal_count":len(signals)})
        return {"status":state,"contradictions":len(contradictions)}
