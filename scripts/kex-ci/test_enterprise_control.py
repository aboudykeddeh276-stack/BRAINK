import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.control_plane import *
from enterprise.payment_entitlement import *
from enterprise.domain_replication import *
from enterprise.distributed_authority import *
from enterprise.recursive_operating_fabric import RecursiveOperatingFabric,FabricNode,OperationalLine,AuthorityContext,LifecycleState,NodeKind,AdmissionError,PromotionError

def check():
    out=[]
    def t(name, cond): out.append((name,bool(cond)))
    ev=Evidence("artifact","casepath","E1",True)
    t("promotion_next_layer", can_promote("DESIGNED","ENCODED",ev,"casepath")[0])
    t("promotion_skip_rejected", not can_promote("DESIGNED","PERSISTED",ev,"casepath")[0])
    t("scope_rejected", not can_promote("DESIGNED","ENCODED",ev,"braink")[0])
    obs=[
      Obligation("blocked",False,True,1,1,1,1,0),
      Obligation("ready-low",True,True,.2,.2,.2,.1,.1),
      Obligation("ready-high",True,True,1,1,1,1,.2),
    ]
    t("selector_feasibility_first", select(obs).id=="ready-high")

    seen=set(); i=Intent("P1","acct","CASEPATH_CLARITY_14900",14900)
    t("authorized_not_entitled", apply_event(i,"e1","AUTHORIZED","r1",seen)["entitled"] is False)
    t("captured_entitles", apply_event(i,"e2","CAPTURED","r1",seen)["entitled"] is True)
    t("idempotent", apply_event(i,"e2","CAPTURED","r1",seen)["status"]=="IDEMPOTENT_REPLAY")
    t("refund_revokes", apply_event(i,"e3","REFUNDED","r1",seen)["entitled"] is False)

    # Process-native execution model: public observation is orthogonal to execution.
    ps=classify_process(mechanism_defined=True,target_bound=True,operation_invoked=True,signal_emitted=True)
    t("process_signaled_without_public_readback", ps=="PROCESS_SIGNALED")
    q=classify_projection({})
    t("public_unobserved_does_not_erase_process", q["state"]=="PUBLIC_PROJECTION_UNOBSERVED" and ps=="PROCESS_SIGNALED")
    q2=classify_projection({"HTTP_READBACK":"PASS"})
    t("http_readback_is_observer_edge", q2["state"]=="PUBLIC_PROJECTION_OBSERVED")
    rec=reconcile(process_state=ps,observations={},conflicts=[])
    t("promotion_can_consume_native_process_evidence_without_public_observation", rec["promotion_state"]=="PROMOTED" and rec["projection_observation_state"]=="PUBLIC_PROJECTION_UNOBSERVED")
    rec2=reconcile(process_state=ps,observations={"HTTP_READBACK":"PASS"},conflicts=["BODY_HASH_MISMATCH"])
    t("public_observation_does_not_override_conflict", rec2["promotion_state"]=="RECONCILIATION_REQUIRED")


    # Recursive operating fabric: state inference is forbidden; deployment requires substrate readback.
    rf=RecursiveOperatingFabric()
    ra=AuthorityContext("authority://root",("deploy","execute","verify","observe"))
    rf.register(FabricNode("build://root",NodeKind.BUILD,None,ra,metadata={"directive_semantic_root":"D1"}))
    for node in [
      FabricNode("skill://s1",NodeKind.SKILL,"build://root",ra.derive("authority://skill",("deploy","execute","verify","observe")),metadata={"directive_semantic_root":"D1"}),
      FabricNode("actuator://a1",NodeKind.ACTUATOR,"build://root",ra.derive("authority://actuator",("deploy","execute")),metadata={"directive_semantic_root":"D1"}),
      FabricNode("substrate://fs",NodeKind.SUBSTRATE,"build://root",ra.derive("authority://substrate",("deploy",)),metadata={"directive_semantic_root":"D1"}),
      FabricNode("runtime://r1",NodeKind.RUNTIME,"build://root",ra.derive("authority://runtime",("execute",)),metadata={"directive_semantic_root":"D1"}),
      FabricNode("observer://o1",NodeKind.OBSERVER,"build://root",ra.derive("authority://observer",("observe",)),metadata={"directive_semantic_root":"D1"}),
      FabricNode("verifier://v1",NodeKind.VERIFIER,"build://root",ra.derive("authority://verifier",("verify",)),metadata={"directive_semantic_root":"D1"}),
      FabricNode("evidence://p1",NodeKind.EVIDENCE,"build://root",ra.derive("authority://evidence",()),metadata={"directive_semantic_root":"D1"}),
    ]: rf.register(node)
    ol=OperationalLine(
      "line://deploy","deploy skill runtime","invoke actuator against explicit substrate",
      "bounded deployment transaction","write target artifact then read back target state",
      "artifact://skill-runtime","artifact materialised and runtime configuration updated","substrate://fs",
      "observer://o1","verifier://v1","target hash and post-state readback match",
      "deployment evidence satisfies DEPLOYED","actuator://a1","substrate://fs","runtime://r1","evidence://p1",
      "retain prior state and return failure receipt","reconcile target and retry bounded transaction")
    rf.add_line("skill://s1",ol); rf.add_line("actuator://a1",ol)
    t("recursive_descendant_admission", rf.descendant_admission("build://root")["admitted"])
    try:
      rf.promote("skill://s1","EXECUTED")
      t("recursive_state_skip_rejected",False)
    except PromotionError:
      t("recursive_state_skip_rejected",True)
    rf.record_evidence("skill://s1","IMPLEMENTED",{"source_ref":"git://repo/path","source_hash":"a"*64,"implementation_readback":"blob:a"})
    rf.promote("skill://s1","IMPLEMENTED")
    rf.record_evidence("skill://s1","EXECUTED",{"command_id":"cmd1","execution_authority":"authority://skill","gate_telemetry":"gate://1","computational_transition":"input->output","post_state_hash":"b"*64,"exit_code":0,"effect_observed":True})
    rf.promote("skill://s1","EXECUTED")
    rf.record_evidence("skill://s1","DEPLOYED",{"target_substrate_id":"substrate://fs","deployment_command_id":"cmd2","realization_readback":False,"target_artifact_hash":"c"*64})
    try:
      rf.promote("skill://s1","DEPLOYED")
      t("recursive_deploy_readback_required",False)
    except PromotionError:
      t("recursive_deploy_readback_required",True)

    t("casepath_claimpath_separate", DOMAIN_BINDINGS["casepath.com.au"] != DOMAIN_BINDINGS["claimpath.org"])
    t("casepath_public_readback_not_gate", CASEPATH_CURRENT_PATCH["public_readback_role"]=="OBSERVER_EDGE_NOT_EXECUTION_GATE")

    p=partition_model()
    t("state_machine_stale_fenced", p["stale_A"]=="FENCED")
    t("state_machine_current_commits", p["current_B"]=="COMMITTED")
    return out, provider_binding_state(os.environ), p

if __name__=="__main__":
    out,bindings,p=check()
    for n,v in out: print(("PASS" if v else "FAIL")+":"+n)
    print("PROVIDERS:"+repr(bindings))
    print("DIST:"+repr(p))
    raise SystemExit(0 if all(v for _,v in out) else 2)
