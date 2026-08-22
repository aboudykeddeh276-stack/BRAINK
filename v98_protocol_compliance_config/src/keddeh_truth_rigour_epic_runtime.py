from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable
import ast, hashlib, json, math, time

def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def root_hash(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()

class ClaimState(str, Enum):
    DEFINED="DEFINED"
    DEVELOPED="DEVELOPED"
    IMPLEMENTED="IMPLEMENTED"
    VERIFIED="VERIFIED"
    ESTABLISHED_PROPERTY="ESTABLISHED_PROPERTY"
    SIMULATION_SUPPORTED="SIMULATION_SUPPORTED"
    OPEN_EMPIRICAL_CLAIM="OPEN_EMPIRICAL_CLAIM"
    CONTRADICTED="CONTRADICTED"

@dataclass(frozen=True)
class Claim:
    identity: str
    proposition: str
    domain: str
    required_predicates: tuple[str,...]
    evidence: tuple[str,...]=()
    counterexamples: tuple[str,...]=()
    state: ClaimState=ClaimState.DEFINED

    def evaluate(self, satisfied: set[str], contradicted: set[str], reproducible: bool=False) -> "Claim":
        if contradicted.intersection(self.required_predicates):
            st=ClaimState.CONTRADICTED
        elif set(self.required_predicates).issubset(satisfied):
            st=ClaimState.ESTABLISHED_PROPERTY if reproducible else ClaimState.VERIFIED
        elif satisfied:
            st=ClaimState.DEVELOPED
        else:
            st=self.state
        return Claim(self.identity,self.proposition,self.domain,self.required_predicates,
                     tuple(sorted(satisfied)),tuple(sorted(contradicted)),st)

@dataclass(frozen=True)
class ObserverFrame:
    identity: str
    origin: tuple[float,float,float]=(0.0,0.0,0.0)
    scale: float=1.0
    def observe(self, point: tuple[float,float,float]) -> tuple[float,float,float]:
        return tuple((point[i]-self.origin[i])/self.scale for i in range(3))

def translate_observation(point, a: ObserverFrame, b: ObserverFrame):
    physical=tuple(point[i]*a.scale+a.origin[i] for i in range(3))
    return b.observe(physical)

def euclidean(v):
    return math.sqrt(sum(x*x for x in v))

def observer_invariant_distance(point_a, point_b, a: ObserverFrame, b: ObserverFrame) -> float:
    pa=tuple(point_a[i]*a.scale+a.origin[i] for i in range(3))
    pb=tuple(point_b[i]*b.scale+b.origin[i] for i in range(3))
    return euclidean(tuple(pa[i]-pb[i] for i in range(3)))

class KState(str, Enum):
    NEG3="-3"; NEG2="-2"; ONE="1"; POS2="+2"; POS3="+3"

class SemanticStateKind(str, Enum):
    PRESENT="PRESENT"
    REFERENCE_ZERO="REFERENCE_ZERO"
    NO_CHANGE="NO_CHANGE"
    ABSENT="ABSENT"
    ERROR="ERROR"

@dataclass(frozen=True)
class SemanticState:
    kind: SemanticStateKind
    value: str|None=None
    frame: str|None=None
    @staticmethod
    def present(value: KState) -> "SemanticState":
        if not isinstance(value,KState): raise TypeError("PRESENT requires KState")
        return SemanticState(SemanticStateKind.PRESENT,value.value,None)
    @staticmethod
    def reference_zero(frame: str) -> "SemanticState":
        return SemanticState(SemanticStateKind.REFERENCE_ZERO,None,frame)

def _present_zero_rejected():
    try:
        SemanticState.present("0")  # type: ignore[arg-type]
        return False
    except TypeError:
        return True

def exhaustive_zero_state_proof():
    vals=list(KState)
    return {
        "state_count":len(vals),
        "ordered_pairs":len(vals)*len(vals),
        "zero_is_weighted_state":any(v.value=="0" for v in vals),
        "reference_zero_separate_type":SemanticState.reference_zero("O").kind.value=="REFERENCE_ZERO",
        "present_zero_rejected":_present_zero_rejected(),
    }

@dataclass
class LexicalNode:
    term: str
    definition: str
    role: str
    source: str
    address: dict[str,Any]

class LexiconILLLM:
    def __init__(self, identity="BRAINK_ILLLM_EPIC_V1"):
        self.identity=identity
        self.lexicon:dict[str,LexicalNode]={}
        self.relations:list[dict[str,Any]]=[]
        self.chains:dict[str,dict[str,Any]]={}
        self.clock=0
        self.root=root_hash({"identity":identity})
    def define(self, term, definition, role, source="local"):
        self.clock+=1
        parent=self.root if not self.lexicon else list(self.lexicon.values())[-1].address["K"]
        seed={"term":term,"definition":definition,"role":role,"source":source,"T":self.clock,"P":parent}
        k=root_hash(seed)
        addr={"N":term,"R":"LEXICON","L":role,"G":"BRAINK_EPIC","T":self.clock,"K":k,"P":parent}
        node=LexicalNode(term,definition,role,source,addr)
        self.lexicon[term]=node
        return node
    def relate(self,a,relation,b,property_scope="semantic"):
        rec={"a":a,"relation":relation,"b":b,"property":property_scope,
             "root":root_hash([a,relation,b,property_scope])}
        self.relations.append(rec); return rec
    def bilateral(self,a,b,forward:Callable[[Any],Any],reverse:Callable[[Any],Any],samples:list[Any]):
        results=[]
        for x in samples:
            y=forward(x); x2=reverse(y)
            results.append({"source":x,"translated":y,"returned":x2,"preserved":x2==x})
        receipt={"a":a,"b":b,"samples":results,"all_preserved":all(x["preserved"] for x in results)}
        receipt["root"]=root_hash(receipt)
        return receipt
    def chain(self,name,terms,intent):
        missing=[t for t in terms if t not in self.lexicon]
        if missing: raise KeyError(f"undefined terms: {missing}")
        steps=[]; prev=None
        for i,t in enumerate(terms):
            n=self.lexicon[t]
            step={"i":i,"term":t,"address":n.address,"parent_step":prev}
            step["root"]=root_hash(step); prev=step["root"]; steps.append(step)
        c={"name":name,"intent":intent,"steps":steps}; c["root"]=root_hash(c); self.chains[name]=c; return c
    def snapshot(self):
        obj={"identity":self.identity,"root":self.root,
             "lexicon":{k:asdict(v) for k,v in self.lexicon.items()},
             "relations":self.relations,"chains":self.chains,"clock":self.clock}
        obj["proof"]=root_hash(obj); return obj

class Multiplex:
    def __init__(self, lane_count:int):
        if lane_count<1: raise ValueError("lane_count")
        self.lane_count=lane_count
    def partition(self, work:list[Any]):
        lanes={i:[] for i in range(self.lane_count)}
        for idx,item in enumerate(work): lanes[idx%self.lane_count].append(item)
        return lanes
    @staticmethod
    def verify_partition(work,lanes):
        flat=[x for lane in lanes.values() for x in lane]
        return {"complete":sorted(map(str,flat))==sorted(map(str,work)),
                "no_duplicate_assignment":len(flat)==len(set(map(canonical,flat))),
                "lane_roots":{str(k):root_hash(v) for k,v in lanes.items()}}

def ingest_python(path: Path):
    src=path.read_text(encoding="utf-8"); tree=ast.parse(src); symbols=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            symbols.append({"name":n.name,"kind":type(n).__name__,"line":getattr(n,"lineno",None)})
    return {"path":str(path),"sha256":hashlib.sha256(src.encode()).hexdigest(),"symbols":symbols,"symbol_count":len(symbols)}

def ingest_codebase(root: Path):
    files=[]
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" not in p.parts: files.append(ingest_python(p))
    obj={"root":str(root),"files":files,"file_count":len(files),"symbol_count":sum(x["symbol_count"] for x in files)}
    obj["proof"]=root_hash(obj); return obj

def capability_delta(before:dict[str,Any],after:dict[str,Any]):
    b={(f["path"],s["name"],s["kind"]) for f in before["files"] for s in f["symbols"]}
    a={(f["path"],s["name"],s["kind"]) for f in after["files"] for s in f["symbols"]}
    added=sorted(a-b); removed=sorted(b-a)
    state="ARCHITECTURE_EVOLVED" if added or removed else "NO_OBSERVED_CAPABILITY_DELTA"
    return {"state":state,"added":added,"removed":removed,"root":root_hash([added,removed,state])}

def simple_three_body_accelerations(masses, positions, G=1.0):
    acc=[]
    for i,ri in enumerate(positions):
        ai=[0.0,0.0,0.0]
        for j,rj in enumerate(positions):
            if i==j: continue
            d=[rj[k]-ri[k] for k in range(3)]; r2=sum(x*x for x in d)
            if r2==0: raise ValueError("collision singularity")
            invr3=1.0/(r2*math.sqrt(r2))
            for k in range(3): ai[k]+=G*masses[j]*d[k]*invr3
        acc.append(tuple(ai))
    return acc

def force_balance_residual(masses, positions):
    acc=simple_three_body_accelerations(masses,positions)
    total=[sum(masses[i]*acc[i][k] for i in range(len(masses))) for k in range(3)]
    return euclidean(tuple(total))

def write_json(path:Path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

def activate(root:Path):
    lex=LexiconILLLM()
    foundations=[
        ("truth","property-scoped correspondence between a claim and its defined evidence conditions","EPISTEMIC"),
        ("rigour","truthfulness plus explicit scope, evidence, reproducibility, falsifiability and method","EPISTEMIC"),
        ("observer","frame/context that defines a representation without becoming the represented object","OBSERVER_STATE"),
        ("reference_zero","observer/calibration reference distinct from weighted presence state","ZERO_STATE"),
        ("multiplex","recoverable composition of distinct work trajectories over a shared substrate","CONCURRENCY"),
        ("lexicon","typed definition and relation fabric","IL_LLM"),
        ("code","executable mechanism represented with source provenance and relations","DYNAMIC_CODE"),
        ("evidence","observed result bound to a stated property and lineage","PROOF")]
    for x in foundations: lex.define(*x,source="BRAINK_EPIC_V1")
    for a,r,b,p in [("truth","REQUIRED_BY","rigour","claim_quality"),("observer","QUALIFIES","reference_zero","state_semantics"),("lexicon","RESOLVES","code","dynamic_codebase"),("evidence","QUALIFIES","truth","epistemic_state"),("multiplex","EXECUTES_OVER","code","runtime")]: lex.relate(a,r,b,p)
    chain=lex.chain("TRUTHFUL_RIGOROUS_EPIC",["truth","rigour","lexicon","code","multiplex","evidence"],"Preserve truth conditions while turning learned definitions into executed evidence-bearing work.")
    bilateral=lex.bilateral("roman","arabic",lambda x:{"I":1,"V":5,"X":10}.get(x),lambda x:{1:"I",5:"V",10:"X"}.get(x),["I","V","X"])
    zero=exhaustive_zero_state_proof()
    mux=Multiplex(5); work=list(range(50)); lanes=mux.partition(work); muxproof=mux.verify_partition(work,lanes)
    obsA=ObserverFrame("A",(0,0,0),1); obsB=ObserverFrame("B",(10,-5,2),2); physical=(12.0,1.0,4.0)
    a=obsA.observe(physical); b=obsB.observe(physical)
    observer_receipt={"A":a,"B":b,"B_from_A":translate_observation(a,obsA,obsB),"physical_residual":observer_invariant_distance(a,b,obsA,obsB)}
    sim={"force_balance_residual":force_balance_residual([1,1,1],[(1,0,0),(-0.5,0.866025403784,0),(-0.5,-0.866025403784,0)])}
    receipt={"activated_at":time.time(),"lexicon_proof":lex.snapshot()["proof"],"chain_root":chain["root"],"bilateral":bilateral,"zero":zero,"multiplex":muxproof,"observer":observer_receipt,"simulation":sim}
    receipt["proof"]=root_hash(receipt)
    write_json(root/"runtime_volume/lexicon/current.json",lex.snapshot())
    write_json(root/"runtime_volume/multiplex/current.json",{"lanes":lanes,"verification":muxproof})
    write_json(root/"runtime_volume/simulation/current.json",sim)
    write_json(root/"evidence/truth_rigour_epic_activation_receipt.json",receipt)
    return receipt

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--root",default="."); ap.add_argument("--activate",action="store_true"); ap.add_argument("--ingest-self",action="store_true"); args=ap.parse_args(); R=Path(args.root)
    if args.activate: print(json.dumps(activate(R),indent=2,default=str))
    if args.ingest_self:
        graph=ingest_codebase(R); write_json(R/"runtime_volume/code_graph/truth_rigour_epic_current.json",graph); print(json.dumps(graph,indent=2))
