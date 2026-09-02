from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Optional
import hashlib, json, time, uuid

def _bytes(x: Any)->bytes:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def root(x: Any)->str:
    return hashlib.sha256(x if isinstance(x,bytes) else _bytes(x)).hexdigest()

class MutationClass(str,Enum):
    UPDATE="UPDATE"
    AMENDMENT="AMENDMENT"
    EVOLUTION="EVOLUTION"

class ObjectState(str,Enum):
    RESIDENT="RESIDENT"
    HOLE="HOLE"
    BOUND="BOUND"
    EXECUTED="EXECUTED"
    SIGNALED="SIGNALED"
    SUPERSEDED="SUPERSEDED"

@dataclass
class RuntimeObject:
    object_id:str
    class_id:str
    identity_root:str
    revision:int
    state:ObjectState
    payload:Dict[str,Any]
    predecessor_id:Optional[str]=None
    successor_id:Optional[str]=None

@dataclass(frozen=True)
class ObserverEdge:
    edge_id:str
    subject_id:str
    source:str
    kind:str
    payload_hash:str
    created_ns:int

class EvolutionFabric:
    """UPDATE preserves identity; AMENDMENT changes a bounded graph region; EVOLUTION creates a lineage-linked successor."""
    def __init__(self):
        self.objects:Dict[str,RuntimeObject]={}
        self.addresses:Dict[str,str]={}
        self.holes:Dict[str,Dict[str,Any]]={}
        self.observers:list[ObserverEdge]=[]
        self.ledger:list[Dict[str,Any]]=[]
        self.tick=0

    def _emit(self,event_type,subject_id,address,payload):
        self.tick+=1
        event={"seq":self.tick,"event_type":event_type,"subject_id":subject_id,"address":address,"payload":payload,"created_ns":time.time_ns()}
        event["event_root"]=root(event)
        self.ledger.append(event)

    def create(self,class_id,address,payload):
        oid=f"OBJ-{uuid.uuid4().hex[:12]}"
        obj=RuntimeObject(oid,class_id,root({"class":class_id,"seed":payload}),1,ObjectState.RESIDENT,payload)
        self.objects[oid]=obj; self.addresses[address]=oid
        self._emit("CREATE",oid,address,{"payload_root":root(payload)})
        return obj

    def resolve(self,address):
        oid=self.addresses.get(address)
        if oid: return {"status":"RESOLVED","object":self.objects[oid]}
        hole=self.holes.setdefault(address,{"address":address,"state":"HOLE","attempts":0,"created_ns":time.time_ns()})
        hole["attempts"]+=1
        self._emit("HOLE_RESOLVED_AS_STATE",None,address,{"attempt":hole["attempts"]})
        return {"status":"HOLE","hole":dict(hole)}

    def bind_hole(self,address,object_id):
        if object_id not in self.objects: raise KeyError(object_id)
        self.addresses[address]=object_id; self.holes.pop(address,None)
        self._emit("HOLE_BOUND",object_id,address,{})

    def classify(self,subject_id,target_address,payload,reason=""):
        topology_change=bool(payload.get("new_class_id") or payload.get("new_addresses") or payload.get("carrier_schema"))
        bounded_patch=bool(payload.get("patch_id") or payload.get("graph_node") or payload.get("additive"))
        if topology_change: return MutationClass.EVOLUTION
        if bounded_patch: return MutationClass.AMENDMENT
        return MutationClass.UPDATE

    def dispatch(self,subject_id,target_address,payload,reason=""):
        if subject_id not in self.objects: raise KeyError(subject_id)
        obj=self.objects[subject_id]
        mc=self.classify(subject_id,target_address,payload,reason)
        if obj.state==ObjectState.SUPERSEDED and mc in {MutationClass.UPDATE,MutationClass.AMENDMENT}:
            return {"status":"REJECTED_SUPERSEDED_IDENTITY","class":mc.value,"object_id":subject_id}
        if mc is MutationClass.UPDATE:
            before=root(obj.payload); obj.payload={**obj.payload,**payload}; obj.revision+=1; obj.state=ObjectState.EXECUTED; after=root(obj.payload)
            self._emit("UPDATE",obj.object_id,target_address,{"before":before,"after":after})
            return {"status":"EXECUTED","class":"UPDATE","object_id":obj.object_id,"before":before,"after":after,"revision":obj.revision}
        if mc is MutationClass.AMENDMENT:
            before=root(obj.payload); amendments=list(obj.payload.get("_amendments",[])); amendments.append({"target_address":target_address,"patch":payload,"prior_payload_root":before,"created_ns":time.time_ns()}); obj.payload={**obj.payload,"_amendments":amendments}
            node=payload.get("graph_node")
            if node:
                graph=dict(obj.payload.get("graph",{})); prior=graph.get(node); graph[node]={"prior":prior,"amendment":payload}; obj.payload["graph"]=graph
            obj.revision+=1; obj.state=ObjectState.SIGNALED; after=root(obj.payload)
            self._emit("AMENDMENT",obj.object_id,target_address,{"before":before,"after":after,"patch_id":payload.get("patch_id")})
            return {"status":"SIGNALED","class":"AMENDMENT","object_id":obj.object_id,"before":before,"after":after,"revision":obj.revision}
        pred=obj; new_class=payload.get("new_class_id",pred.class_id); successor_payload={"evolved_from":pred.object_id,"predecessor_root":root(pred.payload),"base_payload":pred.payload,"evolution":payload}
        sid=f"OBJ-{uuid.uuid4().hex[:12]}"; succ=RuntimeObject(sid,new_class,root({"class":new_class,"seed":successor_payload}),1,ObjectState.RESIDENT,successor_payload,predecessor_id=pred.object_id)
        pred.successor_id=sid; pred.state=ObjectState.SUPERSEDED; self.objects[sid]=succ; self.addresses[target_address]=sid
        for a in payload.get("new_addresses",[]): self.addresses[a]=sid
        self._emit("EVOLUTION",sid,target_address,{"predecessor_id":pred.object_id,"successor_id":sid,"class_id":new_class})
        return {"status":"SUCCESSOR_CREATED","class":"EVOLUTION","predecessor_id":pred.object_id,"successor_id":sid,"successor_class":new_class}

    def observe(self,subject_id,source,kind,payload):
        edge=ObserverEdge(f"OBS-{uuid.uuid4().hex[:12]}",subject_id,source,kind,root(payload),time.time_ns()); self.observers.append(edge)
        self._emit("OBSERVER_EDGE",subject_id,source,{"kind":kind,"payload_hash":edge.payload_hash})
        return edge

    @property
    def carrier(self):
        return {"tick":self.tick,"object_root":root({k:asdict(v) for k,v in sorted(self.objects.items())}),"address_root":root(self.addresses),"hole_root":root(self.holes),"observer_root":root([asdict(o) for o in self.observers]),"ledger_root":root(self.ledger),"current_addresses":dict(self.addresses)}
