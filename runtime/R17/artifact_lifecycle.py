from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional
import hashlib, json, time, uuid

def sha(v):
    raw=v if isinstance(v,bytes) else json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class ArtifactEvent:
    event_id:str
    artifact_id:str
    path:str
    state:str
    content_root:str
    parent_root:Optional[str]
    operation:str
    created_ns:int

class ArtifactLifecycleLedger:
    VALID=("DISCOVERED","INGESTED","VALIDATED","RELEASE_CANDIDATE","RELEASED","QUARANTINED","SUPERSEDED","ROLLED_BACK")
    def __init__(self):
        self.events=[]; self.current={}
    def record(self,artifact_id,path,state,content,operation):
        if state not in self.VALID: raise ValueError(state)
        prior=self.current.get(artifact_id)
        e=ArtifactEvent("AE-"+uuid.uuid4().hex[:12],artifact_id,str(Path(path)),state,sha(content),prior.content_root if prior else None,operation,time.time_ns())
        self.events.append(e); self.current[artifact_id]=e
        return asdict(e)
    def snapshot(self):
        return {"artifact_count":len(self.current),"event_count":len(self.events),"root":sha([asdict(e) for e in self.events]),"current":{k:asdict(v) for k,v in sorted(self.current.items())}}
