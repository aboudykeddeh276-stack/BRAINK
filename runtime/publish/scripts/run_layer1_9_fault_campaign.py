from __future__ import annotations
import json, random, tempfile
from dataclasses import asdict
from braink_runtime.layer1_9_reconciler import Layer1to9Reconciler, LayerViolation, digest
from braink_runtime.full_suite_kernel import ResidentBRAINKAdapters
from braink_runtime.layer2_reconciler import ObservedManifestation

random.seed(297)
results=[]

def record(name, ok, detail):
    results.append({"scenario":name,"status":"PASS" if ok else "FAIL","detail":detail})

def payloads(tag="A"):
    return {
        1: {"payload_hash": "a"*64, "payload_bytes": 10, "media_type": "application/octet-stream"},
        2: {"actor_id": "node:A", "authority_ref": "authority://test", "capability": "EXECUTE"},
        3: {"coordinate": "X2/Y2", "directory_root": digest({"d": tag}), "coordinate_generation": 1},
        4: {"mapping": "logical-coordinate", "origin": "Singularity:1", "geometry_root": digest({"g": tag})},
        5: {"route_id": "route:test", "signal_type": "EXECUTE", "destination": "runtime://test"},
        6: {"epoch": 1, "index": 1, "commit_root": digest({"c": tag}), "quorum_size": 2, "membership_hash": digest({"m": tag}), "certificate_hash": digest({"qc": tag}), "receipt_hash": digest({"receipt": tag})},
        7: {"operation": "EXECUTE", "target": "runtime://test", "result_root": digest({"r": tag})},
        8: {"observer_id": "observer://test", "before_root": digest({"x":1}), "after_root": digest({"x":2}), "changed": True},
        9: {"evidence_root": digest({"e": tag}), "receipt_count": 8, "claim_state": "OBSERVED"},
    }

for layer in range(1,10):
    r=Layer1to9Reconciler()
    try:
        r.reconcile_all(run_id=f"fault:{layer}",generation=1,payloads=payloads(),fault_layer=layer)
        record(f"layer_{layer}_fault","FAIL",{"observed":"NO_EXCEPTION"})
    except LayerViolation as exc:
        expected_prefix=set(range(1,layer))
        record(
            f"layer_{layer}_fault",
            set(r.state)==expected_prefix and (r.failures and r.failures[-1].layer==layer),
            {"error":str(exc),"committed_layers":sorted(r.state),"expected_prefix":sorted(expected_prefix)}
        )

retry_pass=0
for layer in range(1,10):
    r=Layer1to9Reconciler()
    try:r.reconcile_all(run_id=f"retry:{layer}",generation=1,payloads=payloads(),fault_layer=layer)
    except LayerViolation:pass
    try:
        r.reconcile_all(run_id=f"retry:{layer}",generation=1,payloads=payloads())
        if r.verify_chain()==r.root: retry_pass+=1
    except Exception: pass
record("all_layer_transient_retry",retry_pass==9,{"converged":retry_pass,"trials":9})

conflicts=0
for layer in range(1,10):
    r=Layer1to9Reconciler();p=payloads();r.reconcile_all(run_id=f"conflict:{layer}",generation=1,payloads=p)
    q=payloads()
    if layer==1:q[1]["media_type"]="text/plain"
    elif layer==2:q[2]["authority_ref"]="authority://other"
    elif layer==3:q[3]["directory_root"]=digest({"d":"other"})
    elif layer==4:q[4]["geometry_root"]=digest({"g":"other"})
    elif layer==5:q[5]["route_id"]="route:other"
    elif layer==6:q[6]["commit_root"]=digest({"c":"other"})
    elif layer==7:q[7]["result_root"]=digest({"r":"other"})
    elif layer==8:q[8]["observer_id"]="observer://other"
    else:q[9]["evidence_root"]=digest({"e":"other"})
    try:r.reconcile_all(run_id=f"conflict:{layer}",generation=1,payloads=q)
    except LayerViolation as exc:
        if "SAME_GENERATION_PAYLOAD_CONFLICT" in str(exc): conflicts+=1
record("same_generation_mutation_fencing",conflicts==9,{"rejected":conflicts,"trials":9})

tamper_blocks=0
for _ in range(180):
    layer=random.randint(1,9)
    r=Layer1to9Reconciler();r.reconcile_all(run_id=f"tamper:{_}",generation=1,payloads=payloads())
    bad=r._committed[layer]
    object.__setattr__(bad,"receipt_hash","f"*64)
    try:r.verify_chain()
    except LayerViolation:tamper_blocks+=1
record("random_receipt_tamper",tamper_blocks==180,{"blocked":tamper_blocks,"trials":180})

lies=0
for changed,before,after in [
    (False,digest({"x":1}),digest({"x":2})),
    (True,digest({"x":1}),digest({"x":1})),
]:
    p=payloads();p[8].update({"changed":changed,"before_root":before,"after_root":after})
    try:Layer1to9Reconciler().reconcile_all(run_id=f"lie:{lies}",generation=1,payloads=p)
    except LayerViolation:lies+=1
record("observation_lie_detection",lies==2,{"blocked":lies,"trials":2})

class FlakyActuator:
    def __init__(self, probability):
        self.probability=probability;self.seen={}
    def execute(self,a,key):
        if key in self.seen:return self.seen[key]
        if random.random()<self.probability:raise RuntimeError("transient actuator fault")
        obs=ObservedManifestation(a.manifestation_id,a.endpoint,a.generation,"ATTACHED")
        self.seen[key]=obs;return obs

resident_runs=100;committed=0;failed=0;evidence_leaks=0
for n in range(resident_runs):
    with tempfile.TemporaryDirectory() as td:
        actuator=FlakyActuator(.30)
        a=ResidentBRAINKAdapters(("A","B","C"),f"{td}/evidence.jsonl",actuator)
        try:
            a.kernel().execute(
                run_id=f"resident:{n}",coordinate=f"X{n+2}/Y2",generation=1,actor_id="A",
                authority_ref="authority://resident",payload=f"payload:{n}".encode(),
                media_type="application/octet-stream",operation="MATERIALISE",
                target="runtime://resident",route_id="route://resident"
            )
            committed+=1
            if len(a.journal.recover())!=1:evidence_leaks+=1
        except Exception:
            failed+=1
            if len(a.journal.recover())!=0:evidence_leaks+=1
record("resident_l2_fault_evidence_boundary",evidence_leaks==0,{"runs":resident_runs,"committed":committed,"failed":failed,"evidence_boundary_violations":evidence_leaks})

summary={"schema":"braink.report03.layer1-9-fault-campaign.v2","seed":297,"scenarios":len(results),"passed":sum(x["status"]=="PASS" for x in results),"failed":sum(x["status"]=="FAIL" for x in results),"results":results}
print(json.dumps(summary,indent=2))
raise SystemExit(1 if summary["failed"] else 0)
