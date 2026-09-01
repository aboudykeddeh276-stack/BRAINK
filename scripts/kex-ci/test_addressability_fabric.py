import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.addressability_fabric import AddressabilityFabric, AddressState

results=[]
def t(name,cond): results.append((name,bool(cond)))

f=AddressabilityFabric()
a=f.map("KEX://CASEPATH/UNBOUND")
t("absence_becomes_hole", a.state==AddressState.HOLE)
r=f.apply("KEX://CASEPATH/UNBOUND","WRITE",{"x":1})
t("hole_is_routable_state", r["status"]=="HOLE" and len(f.queue)==1)

store=f.create_backing("vfs://ring2/main")
f.register_backing_adapter("adapter://vfs/ring2","vfs://ring2/main")
b=f.map("KEX://CASEPATH/YOUR-DATA",aperture="aperture://casepath/your-data",backing="vfs://ring2/main",adapter="adapter://vfs/ring2")
t("aperture_bound", b.aperture=="aperture://casepath/your-data")
payload={"patch_id":"CP-TC-20260727-C01","target":"/your-data.html"}
w=f.apply("KEX://CASEPATH/YOUR-DATA","WRITE",payload)
t("write_through_aperture", w["status"]=="COMMITTED")
t("ring2_contains_payload", store.objects["KEX://CASEPATH/YOUR-DATA"]==payload)

tick=f.carrier.tick
sig=f.observe("public://casepath.com.au","KEX://CASEPATH/YOUR-DATA","HTTP_READBACK",{"status":200})
t("observer_absorbed", sig.kind=="HTTP_READBACK")
t("observer_not_execution_gate", f.carrier.tick==tick+1)

f.map("KEX://REMOTE/FUTURE",aperture="aperture://future",adapter="adapter://missing")
u=f.apply("KEX://REMOTE/FUTURE","READ")
t("missing_adapter_explicit", u["status"]=="UNRESOLVED_ADAPTER")

for n,c in results: print(("PASS" if c else "FAIL")+":"+n)
raise SystemExit(0 if all(c for _,c in results) else 2)
