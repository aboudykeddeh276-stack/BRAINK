"""BRAINK/KEX deterministic system evolution control plane R1.
Generated from validated modules; source package remains authoritative."""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Iterable
import hashlib, json, os, tempfile, time


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))

def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

@dataclass(frozen=True)
class Artifact:
    identity: str; path: str; sha256: str; bytes: int; kind: str; lineage_parent: str|None=None
    @staticmethod
    def from_path(path: Path, identity: str, kind: str, lineage_parent: str|None=None):
        raw=path.read_bytes(); return Artifact(identity,str(path.resolve()),sha256_bytes(raw),len(raw),kind,lineage_parent)

@dataclass(frozen=True)
class Event:
    seq:int; ts_ns:int; event_type:str; subject:str; payload:dict[str,Any]; prev_hash:str; event_hash:str

class ImmutableLedger:
    def __init__(self,path:Path):
        self.path=path; self.events=[]
        if path.exists(): self._load()
    def _load(self):
        prev="GENESIS"
        for idx,line in enumerate(self.path.read_text().splitlines(),1):
            if not line.strip(): continue
            raw=json.loads(line); supplied=raw.pop("event_hash"); expected=sha256_json(raw)
            if supplied!=expected or raw["prev_hash"]!=prev: raise ValueError(f"ledger integrity failure at record {idx}")
            event=Event(event_hash=supplied,**raw); self.events.append(event); prev=supplied
    @property
    def head(self): return self.events[-1].event_hash if self.events else "GENESIS"
    def append(self,event_type,subject,payload):
        body={"seq":len(self.events)+1,"ts_ns":time.time_ns(),"event_type":event_type,"subject":subject,"payload":payload,"prev_hash":self.head}
        event=Event(event_hash=sha256_json(body),**body)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("a",encoding="utf-8") as f:
            f.write(canonical_json(asdict(event))+"\n"); f.flush(); os.fsync(f.fileno())
        self.events.append(event); return event

class DeterministicVFS:
    def __init__(self): self._entries={}
    @staticmethod
    def _validate(path):
        if not path.startswith("/") or ".." in Path(path).parts: raise ValueError(f"invalid VFS path: {path}")
    def write(self,path,value,*,kind="json",source=None):
        self._validate(path); entry={"value":value,"sha256":sha256_json(value),"kind":kind,"source":source}; self._entries[path]=entry; return entry
    def read(self,path): self._validate(path); return self._entries[path]["value"]
    def paths(self): return sorted(self._entries)
    def snapshot(self): return {p:self._entries[p] for p in self.paths()}
    def root(self): return sha256_json(self.snapshot())
    def checkpoint(self,path:Path):
        doc={"schema":"braink.vfs.checkpoint.v1","root":self.root(),"entries":self.snapshot()}; atomic_write(path,canonical_json(doc).encode()); return doc["root"]
    @classmethod
    def restore(cls,path:Path):
        doc=json.loads(path.read_text()); v=cls(); v._entries=doc["entries"]
        if v.root()!=doc["root"]: raise ValueError("checkpoint root mismatch")
        return v

@dataclass(frozen=True)
class ModuleContract:
    module_id:str; depends_on:tuple[str,...]; execute:Callable[[dict[str,Any]],dict[str,Any]]

class Orchestrator:
    def __init__(self,ledger,vfs): self.ledger=ledger; self.vfs=vfs; self.modules={}
    def register(self,c):
        if c.module_id in self.modules: raise ValueError(f"duplicate module: {c.module_id}")
        self.modules[c.module_id]=c
    def order(self,selected=None):
        expanded=set()
        def include(mid):
            if mid not in self.modules: raise KeyError(mid)
            if mid in expanded:return
            expanded.add(mid)
            for dep in self.modules[mid].depends_on: include(dep)
        for mid in set(selected or self.modules): include(mid)
        visiting=set(); visited=set(); ordered=[]
        def visit(mid):
            if mid in visiting: raise ValueError(f"cycle detected at {mid}")
            if mid in visited:return
            visiting.add(mid)
            for dep in self.modules[mid].depends_on: visit(dep)
            visiting.remove(mid); visited.add(mid); ordered.append(mid)
        for mid in sorted(expanded): visit(mid)
        return ordered
    def run(self,selected=None):
        results={}
        for mid in self.order(selected):
            c=self.modules[mid]; inputs={d:results[d] for d in c.depends_on}; self.ledger.append("MODULE_STARTED",mid,{"dependencies":list(c.depends_on)})
            out=c.execute(inputs); self.vfs.write(f"/runtime/modules/{mid}.json",out,source=mid); self.ledger.append("MODULE_COMPLETED",mid,{"output_hash":sha256_json(out)}); results[mid]=out
        return results

def reconcile(left,right):
    delta=[{"key":k,"left":left.get(k),"right":right.get(k)} for k in sorted(set(left)|set(right)) if left.get(k)!=right.get(k)]
    return {"schema":"braink.reconciliation.v1","equal":not delta,"left_root":sha256_json(left),"right_root":sha256_json(right),"delta":delta}

def capability_score(metrics):
    weights={"functional":.25,"deterministic":.20,"recoverable":.15,"observable":.15,"secure":.15,"deployable":.10}
    if set(metrics)!=set(weights): raise ValueError("capability metric set mismatch")
    n={k:min(1,max(0,float(v))) for k,v in metrics.items()}; score=sum(n[k]*weights[k] for k in weights)
    return {"schema":"braink.market-capability.v1","score":round(score,6),"metrics":n,"weights":weights,"market_ready":score>=.85 and min(n.values())>=.70}

@dataclass(frozen=True)
class Candidate:
    lane:str; payload:dict[str,Any]; root:str

class CognitiveRefraction:
    def __init__(self): self._lanes={}
    def register(self,name,lane):
        if name in self._lanes: raise ValueError(f"duplicate lane: {name}")
        self._lanes[name]=lane
    def run(self,state):
        return [Candidate(name,out:=self._lanes[name](state),sha256_json(out)) for name in sorted(self._lanes)]
    @staticmethod
    def reconcile(candidates):
        if not candidates: raise ValueError("no candidates")
        groups={}
        for c in candidates: groups.setdefault(c.root,[]).append(c.lane)
        root,lanes=sorted(groups.items(),key=lambda x:(-len(x[1]),x[0]))[0]; winner=next(c for c in candidates if c.root==root)
        return {"schema":"braink.cognitive-reconciliation.v1","candidate_count":len(candidates),"agreement_count":len(lanes),"agreement_ratio":len(lanes)/len(candidates),"winner_root":root,"supporting_lanes":sorted(lanes),"payload":winner.payload,"promotion_allowed":len(lanes)>len(candidates)/2}

@dataclass(frozen=True)
class GateResult:
    gate:str; passed:bool; evidence:dict[str,Any]

class PromotionPipeline:
    ORDER=("discover","build","test","reconcile","security","checkpoint","deploy","readback")
    def __init__(self): self.gates={}
    def register(self,name,fn):
        if name not in self.ORDER: raise ValueError(name)
        self.gates[name]=fn
    def run(self,state):
        results=[]
        for name in self.ORDER:
            if name not in self.gates: raise ValueError(f"missing promotion gate {name}")
            r=self.gates[name](state); results.append(r)
            if not r.passed: break
        doc={"schema":"braink.promotion-run.v1","gates":[asdict(x) for x in results]}; doc["root"]=sha256_json(doc); doc["promoted"]=len(results)==len(self.ORDER) and all(x.passed for x in results); return doc
