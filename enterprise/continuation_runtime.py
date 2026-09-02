from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any, Dict, Callable
import hashlib,json,time,uuid

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass
class Continuation:
    continuation_id:str
    address:str
    process_id:str
    state:str
    priority:float
    attempts:int
    payload:Dict[str,Any]
    created_ns:int
    updated_ns:int

class ContinuationRuntime:
    def __init__(self):
        self.processes:Dict[str,Callable]={}
        self.queue:Dict[str,Continuation]={}
        self.history=[]
    def register_process(self,process_id,fn):
        self.processes[process_id]=fn
    def enqueue(self,address,process_id,payload,priority=1.0):
        cid=f"continuation://r11/{uuid.uuid4().hex[:12]}"
        now=time.time_ns()
        c=Continuation(cid,address,process_id,"READY",priority,0,payload,now,now)
        self.queue[cid]=c
        return c
    def select(self):
        ready=[c for c in self.queue.values() if c.state=="READY"]
        return None if not ready else sorted(ready,key=lambda c:(-c.priority,c.created_ns,c.continuation_id))[0]
    def tick(self):
        c=self.select()
        if not c: return {"status":"IDLE"}
        fn=self.processes.get(c.process_id)
        c.attempts+=1; c.updated_ns=time.time_ns()
        if not fn:
            c.state="BLOCKED"; result={"status":"UNRESOLVED_PROCESS","process_id":c.process_id}
        else:
            c.state="RUNNING"
            try:
                result=fn(c.payload)
                c.state="COMPLETED" if result.get("status") in {"COMMITTED","EXECUTED","SIGNALED","SUCCESSOR_CREATED","DONE"} else "BLOCKED"
            except Exception as e:
                result={"status":"ERROR","error":type(e).__name__+":"+str(e)}; c.state="FAILED"
        self.history.append({"continuation":asdict(c),"result":result,"result_root":root(result)})
        return {"status":c.state,"continuation_id":c.continuation_id,"result":result}
