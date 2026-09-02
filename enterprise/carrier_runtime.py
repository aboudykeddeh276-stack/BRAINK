from pathlib import Path
from typing import Any,Mapping
import hashlib,json,os,tempfile

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class CarrierRuntime:
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def load(self):
        if not self.path.exists(): return {"schema":"braink.carrier/v1","tick":0,"state":{},"carrier_root":root({})}
        return json.loads(self.path.read_text("utf-8"))
    def rewrite(self,state:Mapping[str,Any]):
        prior=self.load(); frame={"schema":"braink.carrier/v1","tick":prior["tick"]+1,"predecessor_root":prior.get("carrier_root"),"state":dict(state)}
        frame["carrier_root"]=root(frame)
        encoded=json.dumps(frame,sort_keys=True,separators=(",",":")).encode()
        with tempfile.NamedTemporaryFile("wb",dir=self.path.parent,delete=False) as f:
            tmp=Path(f.name); f.write(encoded); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,self.path); return frame
