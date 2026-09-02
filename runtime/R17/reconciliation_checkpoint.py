from __future__ import annotations
from pathlib import Path
import hashlib,json,os

def sha(v):
    raw=v if isinstance(v,bytes) else json.dumps(v,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()

class ReconciliationEngine:
    def compare(self,expected,observed):
        keys=sorted(set(expected)|set(observed)); deltas=[]
        for k in keys:
            if expected.get(k)!=observed.get(k): deltas.append({"key":k,"expected":expected.get(k),"observed":observed.get(k)})
        return {"status":"MATCH" if not deltas else "DELTA","delta_count":len(deltas),"deltas":deltas,"expected_root":sha(expected),"observed_root":sha(observed)}

class CheckpointStore:
    def __init__(self,path): self.path=Path(path)
    def write(self,state):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        raw=json.dumps(state,sort_keys=True,separators=(",",":")); tmp=self.path.with_suffix(self.path.suffix+".tmp")
        tmp.write_text(raw); os.replace(tmp,self.path); readback=self.path.read_text()
        return {"status":"CHECKPOINTED" if readback==raw else "WRITE_FAILED","root":hashlib.sha256(readback.encode()).hexdigest()}
    def read(self):
        if not self.path.exists(): return {"status":"MISSING"}
        data=json.loads(self.path.read_text()); return {"status":"RESTORED","state":data,"root":sha(data)}
