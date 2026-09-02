from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,time

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass
class Binding:
    logical:str
    backing:str
    adapter_id:str
    aperture:str
    bound_ns:int

class AutoBinder:
    def __init__(self,registry):
        self.registry=registry
        self.bindings={}
        self.failures=[]
    def bind(self,logical,backing,operation="WRITE"):
        resolved=self.registry.discover(backing,operation)
        if resolved["status"]!="RESOLVED":
            failure={"logical":logical,"backing":backing,"operation":operation,"result":resolved}
            self.failures.append(failure)
            return {"status":"HOLE_REMAINS",**failure}
        b=Binding(logical,backing,resolved["adapter_id"],f"aperture://auto/{root([logical,backing])[:16]}",time.time_ns())
        self.bindings[logical]=b
        return {"status":"BOUND","binding":b}
    def apply(self,logical,operation,payload=None):
        b=self.bindings.get(logical)
        if not b:
            return {"status":"HOLE","logical":logical,"reason":"NO_BINDING"}
        return self.registry.invoke(b.adapter_id,backing=b.backing,logical=logical,operation=operation,payload=payload)
