import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.control_plane import *
from enterprise.payment_entitlement import *
from enterprise.domain_replication import *
from enterprise.distributed_authority import *

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
    q=qualify({"REGISTRAR":"PASS","DNS":"PASS","INGRESS":"PASS","TLS":"PASS"})
    t("four_receipts_not_live", q["state"]!="PUBLIC_LIVE" and q["missing"]==["HTTP_READBACK"])
    q=qualify({k:"PASS" for k in REQUIRED_RECEIPTS})
    t("five_receipts_live", q["state"]=="PUBLIC_LIVE")
    t("casepath_claimpath_separate", DOMAIN_BINDINGS["casepath.com.au"] != DOMAIN_BINDINGS["claimpath.org"])
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
