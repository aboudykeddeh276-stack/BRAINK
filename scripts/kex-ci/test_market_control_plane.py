import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.identity_policy import *
from enterprise.audit_observability import *
from enterprise.usage_metering import *
from enterprise.deployment_contract import *

T=[]
def t(n,c,d=None): T.append((n,bool(c),d))
p=Principal("agent://casepath","agent","tenant-A",frozenset({"casepath.write","casepath.read"}))
read=Tool("tool://casepath/read","read",frozenset({"casepath.read"}))
write=Tool("tool://casepath/amend","write",frozenset({"casepath.write"}))
t("read_allowed",PolicyEngine().decide(p,read,"tenant-A").allowed)
t("write_requires_approval",PolicyEngine().decide(p,write,"tenant-A").requires_approval)
t("approved_write_allowed",PolicyEngine().decide(p,write,"tenant-A",approved=True).allowed)
t("cross_tenant_denied",not PolicyEngine().decide(p,read,"tenant-B").allowed)

a=AuditLog(); e=a.append("tenant-A",p.principal_id,"AMEND","/your-data.html","ALLOW","COMMITTED","corr-1")
t("audit_correlates",len(a.by_correlation("corr-1"))==1 and len(e.event_root)==64)

m=Metrics();m.inc("deployments");m.observe_ms("actuator_latency",25);m.observe_ms("actuator_latency",35)
s=m.snapshot(); t("metrics_aggregate",s["counters"]["deployments"]==1 and s["durations"]["actuator_latency"]["avg_ms"]==30)

u=UsageMeter();u.record("tenant-A","casepath","actuation",1,25);u.record("tenant-A","casepath","readback",1,5)
t("usage_metered",u.totals("tenant-A")=={"tenant_id":"tenant-A","units":2.0,"cost_minor":30})

bad=qualify_release({"build_receipt":"b"})
t("release_missing_controls_blocked",not bad.ready and "test_receipt" in bad.missing)
good=qualify_release({"build_receipt":"b","test_receipt":"t","artifact_digest":"h","rollback_ref":"r","owner":"team","environment":"production"})
t("release_contract_ready",good.ready)

d=dora_event(100,160,failed=True,recovered_at=220,rework=True)
t("dora_metrics_emitted",d["lead_time_seconds"]==60 and d["recovery_seconds"]==60 and d["rework"] is True)

for n,c,d in T: print(("PASS" if c else "FAIL")+":"+n)
raise SystemExit(0 if all(c for _,c,_ in T) else 2)
