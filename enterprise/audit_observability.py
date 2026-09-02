from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,time,uuid

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",", ":")).encode()).hexdigest()

@dataclass(frozen=True)
class AuditEvent:
    event_id:str
    tenant_id:str
    principal_id:str
    action:str
    resource:str
    decision:str
    outcome:str
    correlation_id:str
    created_ns:int
    event_root:str

class AuditLog:
    def __init__(self): self.events=[]
    def append(self,tenant_id,principal_id,action,resource,decision,outcome,correlation_id):
        body={"tenant_id":tenant_id,"principal_id":principal_id,"action":action,"resource":resource,
              "decision":decision,"outcome":outcome,"correlation_id":correlation_id,"created_ns":time.time_ns()}
        e=AuditEvent("AUD-"+uuid.uuid4().hex[:12],**body,event_root=root(body))
        self.events.append(e); return e
    def by_correlation(self,cid): return [e for e in self.events if e.correlation_id==cid]

class Metrics:
    def __init__(self):
        self.counters={}
        self.durations={}
    def inc(self,name,value=1): self.counters[name]=self.counters.get(name,0)+value
    def observe_ms(self,name,value): self.durations.setdefault(name,[]).append(float(value))
    def snapshot(self):
        return {
          "counters":dict(self.counters),
          "durations":{k:{"count":len(v),"avg_ms":sum(v)/len(v),"max_ms":max(v)} for k,v in self.durations.items() if v}
        }
