from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from enterprise.recursive_operating_fabric import (
    RecursiveOperatingFabric,FabricNode,OperationalLine,AuthorityContext,
    LifecycleState,NodeKind,AdmissionError,PromotionError
)

def line():
    return OperationalLine(
        "line://deploy","deploy skill runtime","invoke actuator against explicit substrate",
        "bounded deployment transaction","write target artifact then read back target state",
        "artifact://skill-runtime","artifact materialised and runtime configuration updated",
        "substrate://fs","observer://o1","verifier://v1",
        "target hash and post-state readback match","deployment evidence packet satisfies DEPLOYED",
        "actuator://a1","substrate://fs","runtime://r1","evidence://p1",
        "retain prior state and return failure receipt","reconcile target and retry bounded transaction"
    )

def fabric():
    f=RecursiveOperatingFabric()
    a=AuthorityContext("authority://root",("deploy","execute","verify","observe"))
    f.register(FabricNode("build://root",NodeKind.BUILD,None,a,metadata={"directive_semantic_root":"D1","revision":1}))
    for n in [
        FabricNode("skill://s1",NodeKind.SKILL,"build://root",a.derive("authority://skill",("deploy","execute","verify","observe")),metadata={"directive_semantic_root":"D1"}),
        FabricNode("actuator://a1",NodeKind.ACTUATOR,"build://root",a.derive("authority://actuator",("deploy","execute")),metadata={"directive_semantic_root":"D1"}),
        FabricNode("substrate://fs",NodeKind.SUBSTRATE,"build://root",a.derive("authority://substrate",("deploy",)),metadata={"directive_semantic_root":"D1"}),
        FabricNode("runtime://r1",NodeKind.RUNTIME,"build://root",a.derive("authority://runtime",("execute",)),metadata={"directive_semantic_root":"D1"}),
        FabricNode("observer://o1",NodeKind.OBSERVER,"build://root",a.derive("authority://observer",("observe",)),metadata={"directive_semantic_root":"D1"}),
        FabricNode("verifier://v1",NodeKind.VERIFIER,"build://root",a.derive("authority://verifier",("verify",)),metadata={"directive_semantic_root":"D1"}),
        FabricNode("evidence://p1",NodeKind.EVIDENCE,"build://root",a.derive("authority://evidence",()),metadata={"directive_semantic_root":"D1"}),
    ]: f.register(n)
    f.add_line("skill://s1",line()); f.add_line("actuator://a1",line())
    return f

def expect(name, fn):
    try: fn(); print("PASS:"+name); return True
    except Exception as e: print("FAIL:"+name+":"+type(e).__name__+":"+str(e)); return False

def check():
    out=[]
    out.append(expect("descendant_admission", lambda: (_ for _ in ()).throw(AssertionError()) if not fabric().descendant_admission("build://root")["admitted"] else None))
    out.append(expect("authority_no_escalation", lambda: _authority_no_escalation()))
    out.append(expect("state_no_skip", lambda: _state_no_skip()))
    out.append(expect("full_evidence_lifecycle", lambda: _full_lifecycle()))
    out.append(expect("deployment_requires_readback", lambda: _deployment_readback()))
    out.append(expect("actor_not_verifier", lambda: _actor_not_verifier()))
    out.append(expect("optimisation_after_mechanics", lambda: _optimisation()))
    out.append(expect("sibling_actuator_continuation", lambda: _sibling()))
    return out

def _authority_no_escalation():
    a=AuthorityContext("root",("read","write"))
    try: a.derive("child",("read","admin"))
    except AdmissionError: return
    raise AssertionError("escalation admitted")

def _state_no_skip():
    f=fabric()
    try: f.promote("skill://s1","EXECUTED")
    except PromotionError: return
    raise AssertionError("state skip admitted")

def _promote_to_integrated(f,n):
    chain=[
      ("IMPLEMENTED",{"source_ref":"git://repo/path","source_hash":"a"*64,"implementation_readback":"blob:a"}),
      ("EXECUTED",{"command_id":"cmd1","execution_authority":"authority://skill","gate_telemetry":"gate://1","computational_transition":"input->output","post_state_hash":"b"*64,"exit_code":0,"effect_observed":True}),
      ("DEPLOYED",{"target_substrate_id":"substrate://fs","deployment_command_id":"cmd2","realization_readback":{"path":"/srv/x","hash":"c"*64},"target_artifact_hash":"c"*64}),
      ("ACTIVE",{"participation_probe":"probe://runtime","heartbeat_observed_at":"2026-09-28T08:00:00+09:30","runtime_identity":"runtime://r1","participating":True}),
      ("FUNCTIONING",{"specified_behavior":"deterministic output","expected_result":{"ok":True},"observed_result":{"ok":True},"behavior_passed":True}),
      ("INTEGRATED",{"integration_edges":["edge://api","edge://vfs"],"edge_readbacks":[True,True]})
    ]
    for s,p in chain: f.record_evidence(n,s,p); f.promote(n,s)

def _full_lifecycle():
    f=fabric(); n="skill://s1"; _promote_to_integrated(f,n)
    f.record_evidence(n,"VERIFIED",{"actor_id":"actor://builder","verifier_id":"verifier://v1","verifier_report_ref":"report://77","post_state_hash":"d"*64,"independent_readback":{"ok":True},"receipt_hash":"e"*64})
    f.promote(n,"VERIFIED")
    f.record_evidence(n,"SUSTAINED",{"observation_count":3,"observation_window":"15m","recovery_procedure":"restart and reconcile","recovery_readback":{"rejoined":True}})
    f.promote(n,"SUSTAINED")
    assert f.nodes[n].state==LifecycleState.SUSTAINED

def _deployment_readback():
    f=fabric(); n="skill://s1"
    f.record_evidence(n,"IMPLEMENTED",{"source_ref":"x","source_hash":"a","implementation_readback":"x"}); f.promote(n,"IMPLEMENTED")
    f.record_evidence(n,"EXECUTED",{"command_id":"c","execution_authority":"a","gate_telemetry":"g","computational_transition":"x","post_state_hash":"h","exit_code":0,"effect_observed":True}); f.promote(n,"EXECUTED")
    f.record_evidence(n,"DEPLOYED",{"target_substrate_id":"s","deployment_command_id":"d","realization_readback":False,"target_artifact_hash":"h"})
    try: f.promote(n,"DEPLOYED")
    except PromotionError: return
    raise AssertionError("deployment promoted without readback")

def _actor_not_verifier():
    f=fabric(); n="skill://s1"; _promote_to_integrated(f,n)
    f.record_evidence(n,"VERIFIED",{"actor_id":"same","verifier_id":"same","verifier_report_ref":"r","post_state_hash":"p","independent_readback":{"ok":True}})
    try: f.promote(n,"VERIFIED")
    except PromotionError: return
    raise AssertionError("self verification admitted")

def _optimisation():
    f=fabric()
    try: f.optimise("skill://s1",{},{"authority":True})
    except PromotionError: pass
    else: raise AssertionError("premature optimisation admitted")
    f.nodes["skill://s1"].state=LifecycleState.FUNCTIONING
    metrics={k:1 for k in ("execution_latency","failure_recovery","idempotency","concurrency","persistence","evidence_completeness","dependency_depth","actuator_reliability","verification_cost")}
    metrics["duplicate_work"]=0
    r=f.optimise("skill://s1",metrics,{"authority":True,"verification":True})
    assert r["requires_redeployment"] is True

def _sibling():
    assert RecursiveOperatingFabric.parent_outcome([
      {"actuator":"a","eligible":True,"status":"FAILED"},
      {"actuator":"b","eligible":True,"status":"FUNCTIONING"},
    ])=="DEGRADED_CONTINUE_ELIGIBLE_PATHS"

if __name__=="__main__":
    ok=check()
    raise SystemExit(0 if all(ok) else 2)
