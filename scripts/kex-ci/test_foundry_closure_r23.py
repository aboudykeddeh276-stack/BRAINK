from pathlib import Path
import tempfile
from enterprise.foundry_closure_r23 import DurableStore,HRSupervisionRuntime,CustomerFileLifecycle,ResearchPromotionGate,PublicationRuntime

with tempfile.TemporaryDirectory() as td:
    store=DurableStore(Path(td)/"state.json")
    hr=HRSupervisionRuntime(store)
    a=hr.acquire("lease-1","supervisor://a","agent://worker",100,now_ns=1000)
    assert a.status=="EXECUTED"
    b=hr.acquire("lease-2","supervisor://b","agent://worker",100,now_ns=1050)
    assert b.status=="REJECTED_ACTIVE_LEASE"
    c=hr.expire_and_replace("agent://worker","lease-2","supervisor://b",100,now_ns=1200)
    assert c.effect["epoch"]==2 and c.effect["status"]=="REHYDRATED"

    cf=CustomerFileLifecycle(store)
    cf.create("customer-file://1","customer://1",{"privacy":True})
    cf.transition("customer-file://1","ACTIVE","intake accepted")
    cf.append_event("customer-file://1","COMMUNICATION",{"channel":"email","event":"welcome"})
    cf.append_event("customer-file://1","BILLING",{"invoice":"INV-1","amount":149})
    cf.append_event("customer-file://1","EXPORT",{"package":"export-1"})
    cf.transition("customer-file://1","CLOSED","service complete")
    cf.transition("customer-file://1","ARCHIVED","retention policy")
    assert store.state["customer_files"]["customer-file://1"]["state"]=="ARCHIVED"

    research=ResearchPromotionGate(store)
    rp=research.evaluate("research://1",[{"claim":"x"}],[{"source":"resident-code"}],[{"status":"PASS"}],"verifier://independent")
    assert rp.effect["state"]=="PROMOTED"
    rr=research.evaluate("research://2",[{"claim":"x"}],[{"source":"resident-code"}],[{"status":"PASS"}],None)
    assert rr.effect["state"]=="REVIEW_REQUIRED"

    pub=PublicationRuntime(store)
    pub.stage("release://1",["vfs://artifact"],"frontage://1",{"authority":"team://release","decision":"APPROVE"})
    internal=pub.publish_internal("release://1","vfs://projection/release-1")
    assert internal.effect["state"]=="INTERNAL_PROJECTED"
    public=pub.request_public_activation("release://1","casepath.com.au",[{"type":"A","value":"203.0.113.10"}],True,None)
    assert public.status=="DEFERRED_EXTERNAL_ACTUATOR"

    state_root=store.state["state_root"]
    reloaded=DurableStore(Path(td)/"state.json")
    assert reloaded.state["state_root"]==state_root
    assert reloaded.state["leases"]["agent://worker"]["epoch"]==2
    assert len(reloaded.state["receipts"])>=15

print("R23_FOUNDRY_CLOSURE_PASS")
