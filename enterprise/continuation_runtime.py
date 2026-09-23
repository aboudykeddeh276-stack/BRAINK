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
    SUCCESS_STATES={"COMMITTED","EXECUTED","SIGNALED","SUCCESSOR_CREATED","DONE"}

    def __init__(self):
        self.processes={}
        self.queue={}
        self.history=[]

    def register_process(self,process_id,fn):
        self.processes[process_id]=fn
        now=time.time_ns()
        for continuation in self.queue.values():
            if continuation.process_id==process_id and continuation.state=="BLOCKED":
                continuation.state="READY"
                continuation.updated_ns=now
        return {"status":"REGISTERED","process_id":process_id}

    def enqueue(self,address,process_id,payload,priority=1.0):
        now=time.time_ns()
        for continuation in self.queue.values():
            if continuation.address==address and continuation.process_id==process_id and continuation.state in {"READY","RUNNING","BLOCKED"}:
                continuation.payload=payload
                continuation.priority=max(float(priority),continuation.priority)
                continuation.updated_ns=now
                if continuation.state=="BLOCKED" and process_id in self.processes:
                    continuation.state="READY"
                return continuation
        cid=f"continuation://r11/{uuid.uuid4().hex[:12]}"
        continuation=Continuation(cid,address,process_id,"READY",float(priority),0,payload,now,now)
        self.queue[cid]=continuation
        return continuation

    def select(self):
        ready=[c for c in self.queue.values() if c.state=="READY"]
        return None if not ready else sorted(ready,key=lambda c:(-c.priority,c.created_ns,c.continuation_id))[0]

    def tick(self):
        continuation=self.select()
        if not continuation:
            return {"status":"IDLE"}
        fn=self.processes.get(continuation.process_id)
        continuation.attempts+=1
        continuation.updated_ns=time.time_ns()
        if not fn:
            continuation.state="BLOCKED"
            result={"status":"UNRESOLVED_PROCESS","process_id":continuation.process_id}
        else:
            continuation.state="RUNNING"
            try:
                result=fn(continuation.payload)
                continuation.state="COMPLETED" if result.get("status") in self.SUCCESS_STATES else "BLOCKED"
            except Exception as exc:
                result={"status":"ERROR","error":type(exc).__name__+":"+str(exc)}
                continuation.state="FAILED"
        self.history.append({"continuation":asdict(continuation),"result":result,"result_root":root(result)})
        terminal=continuation.state in {"COMPLETED","FAILED"}
        if terminal:
            self.queue.pop(continuation.continuation_id,None)
        return {"status":continuation.state,"continuation_id":continuation.continuation_id,"result":result,"retired":terminal}
