import json,os,tempfile,time
from pathlib import Path

class CheckpointSupervisor:
    def __init__(self,path):
        self.path=Path(path).resolve(); self.path.parent.mkdir(parents=True,exist_ok=True)
    def load(self):
        if not self.path.exists(): return {"epoch":0,"step":0,"state":"UNINITIALIZED","continuation":None,"checkpoint":None}
        return json.loads(self.path.read_text("utf-8"))
    def commit(self,step,state,continuation,payload):
        old=self.load()
        frame={"epoch":old["epoch"]+1,"step":step,"state":state,"continuation":continuation,
               "checkpoint":f"KEX://CHECKPOINT/{old['epoch']+1}/{step}","payload":payload,"created_ns":time.time_ns()}
        fd,tmp=tempfile.mkstemp(prefix=".checkpoint-",suffix=".tmp",dir=self.path.parent)
        try:
            with os.fdopen(fd,"w") as f: json.dump(frame,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return frame
