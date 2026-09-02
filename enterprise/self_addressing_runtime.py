from __future__ import annotations
from pathlib import Path
import json,hashlib,time

from enterprise.substrate_adapters import CapabilityRegistry,FileJsonAdapter,SQLiteJsonAdapter,MemoryAdapter
from enterprise.auto_binder import AutoBinder
from enterprise.continuation_runtime import ContinuationRuntime

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class SelfAddressingRuntime:
    def __init__(self,state_path):
        self.state_path=Path(state_path)
        self.registry=CapabilityRegistry()
        self.registry.register(SQLiteJsonAdapter(),priority=10)
        self.registry.register(FileJsonAdapter(),priority=20)
        self.registry.register(MemoryAdapter(),priority=100)
        self.binder=AutoBinder(self.registry)
        self.continuations=ContinuationRuntime()
        self.observers=[]
        self.tick_count=0
    def route(self,logical,backing,operation,payload=None):
        if logical not in self.binder.bindings:
            b=self.binder.bind(logical,backing,operation)
            if b["status"]!="BOUND":
                self.observe("runtime://binder",logical,"HOLE_UNBOUND",b)
                self.checkpoint()
                return b
        result=self.binder.apply(logical,operation,payload)
        self.observe("runtime://adapter",logical,"ADAPTER_RESULT",result)
        self.tick_count+=1
        self.checkpoint()
        return result
    def observe(self,source,subject,kind,payload):
        event={"source":source,"subject":subject,"kind":kind,"payload":payload,"payload_root":root(payload),"at_ns":time.time_ns()}
        self.observers.append(event)
        if kind in {"HOLE_UNBOUND","CONTRADICTION","READBACK_MISMATCH"}:
            self.continuations.enqueue(f"KEX://REPAIR/{subject}","process://runtime/reconcile",{"subject":subject,"signal":event},priority=10.0)
        return event
    def register_reconciler(self,fn):
        self.continuations.register_process("process://runtime/reconcile",fn)
    def continuation_tick(self):
        out=self.continuations.tick(); self.tick_count+=1; self.checkpoint(); return out
    def snapshot(self):
        return {"tick":self.tick_count,"bindings":{k:v.__dict__ for k,v in sorted(self.binder.bindings.items())},"binding_failures":self.binder.failures,"observers":self.observers,"continuations":{k:v.__dict__ for k,v in sorted(self.continuations.queue.items())},"history":self.continuations.history}
    def checkpoint(self):
        self.state_path.parent.mkdir(parents=True,exist_ok=True)
        snap=self.snapshot(); raw=json.dumps(snap,sort_keys=True,separators=(",",":"))
        tmp=self.state_path.with_suffix(".tmp"); tmp.write_text(raw); tmp.replace(self.state_path)
        return {"status":"CHECKPOINTED","state_root":hashlib.sha256(raw.encode()).hexdigest(),"path":str(self.state_path)}
    def restore(self):
        if not self.state_path.exists(): return {"status":"NO_CHECKPOINT"}
        snap=json.loads(self.state_path.read_text())
        from enterprise.auto_binder import Binding
        from enterprise.continuation_runtime import Continuation
        self.binder.bindings={k:Binding(**v) for k,v in snap["bindings"].items()}
        self.binder.failures=list(snap["binding_failures"])
        self.observers=list(snap["observers"])
        self.tick_count=int(snap["tick"])
        self.continuations.queue={k:Continuation(**v) for k,v in snap["continuations"].items()}
        self.continuations.history=list(snap["history"])
        return {"status":"RESTORED","tick":self.tick_count,"state_root":root(snap)}
