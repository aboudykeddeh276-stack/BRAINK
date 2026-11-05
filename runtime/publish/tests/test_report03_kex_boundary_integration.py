import copy
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"runtime"/"publish"/"src"))

from observer2_runtime.kex_symbolic_bridge import ILLLMSemanticDictionary, SemanticEntry, bind_symbol
from braink_runtime.kex_boundary_integration import KEXBoundaryIntegration
from braink_runtime.tot_safety import ToTSafetyKernel, SafetyViolation
from braink_runtime.coordinate_directory import DistributedCoordinateDirectory
from braink_runtime.layer2_reconciler import ObservedManifestation

MEMBERS=("A","B","C")

class Actuator:
    def __init__(self): self.seen={}
    def execute(self,a,key):
        if key in self.seen:return self.seen[key]
        state="DETACHED" if a.kind=="DETACH" else "ATTACHED"
        o=ObservedManifestation(a.manifestation_id,a.endpoint,a.generation,state)
        self.seen[key]=o
        return o

def envelope():
    d=ILLLMSemanticDictionary((SemanticEntry(
        "illlm:op:activate","activate","operation","verb",
        "promote an armed mechanism into activation"
    ),))
    return bind_symbol(d,concept_id="concept:cpu.activate",symbol_id="illlm:op:activate",
                       attributes={"target":"runtime://cpu/core"})

def fixture():
    k=ToTSafetyKernel(MEMBERS); d=DistributedCoordinateDirectory(MEMBERS)
    return k,d,KEXBoundaryIntegration(k,d)

def test_boundary_commits_through_tot_and_directory_then_l2_converges():
    k,d,i=fixture(); e=envelope()
    wire,r=i.commit_envelope(e,actor="A",voters=("A","B"),coordinate="kex://concept/cpu.activate",
                             manifestation_id="kab1-cpu-activate",endpoint="carrier://loopback/kab1",generation=1)
    assert wire.startswith(b"KAB1")
    assert r.semantic_root==e.semantic_root and r.envelope_root==e.envelope_root
    assert d.records["kex://concept/cpu.activate"].manifestations["kab1-cpu-activate"].state=="ATTACHED"
    after,l2=i.reconcile(r,{},Actuator())
    assert l2.status=="PASS" and l2.converged
    assert after["kab1-cpu-activate"].endpoint=="carrier://loopback/kab1"

def test_tampered_tot_receipt_still_fails_closed():
    k,d,i=fixture(); t=k.propose(actor="A",command="DIRECTORY_REGISTER",payload={"coordinate":"kex://tamper"})
    r=k.commit(t,[k.vote("A",t),k.vote("B",t)])
    bad=copy.deepcopy(r); object.__setattr__(bad,"receipt_hash","0"*64)
    try:d.apply(t,bad);assert False
    except SafetyViolation as exc: assert "RECEIPT_HASH_MISMATCH" in str(exc)

def test_zero_coordinate_fails_closed_at_report03_boundary():
    k,d,i=fixture()
    try:i.commit_envelope(envelope(),actor="A",voters=("A","B"),coordinate="0",
                          manifestation_id="kab1-zero",endpoint="carrier://loopback/kab1")
    except SafetyViolation as exc:
        assert "ZERO_NOT_PERMITTED_AS_ADDRESS" in str(exc)
    else: assert False

def test_insufficient_quorum_blocks_boundary_commit():
    k,d,i=fixture()
    try:i.commit_envelope(envelope(),actor="A",voters=("A",),coordinate="kex://no-quorum",
                          manifestation_id="kab1-noq",endpoint="carrier://loopback/kab1")
    except SafetyViolation as exc:
        assert "QUORUM_NOT_REACHED" in str(exc)
    else: assert False

def test_stale_generation_blocks_second_boundary_materialisation():
    k,d,i=fixture(); e=envelope()
    i.commit_envelope(e,actor="A",voters=("A","B"),coordinate="kex://gen",
                      manifestation_id="kab1-gen",endpoint="carrier://loopback/kab1",generation=2)
    try:i.commit_envelope(e,actor="A",voters=("A","B"),coordinate="kex://gen",
                          manifestation_id="kab1-gen",endpoint="carrier://loopback/kab1",generation=1)
    except SafetyViolation as exc:
        assert "STALE_GENERATION" in str(exc)
    else: assert False
