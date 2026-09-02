from pathlib import Path
import concurrent.futures, copy, json, os, sqlite3, subprocess, sys, tempfile, time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.orchestration.durable_execution_r5 import SignedEnvelopeAuthority, DomainAuthorityAtomicCoordinator, CheckpointStore, IntegrityError, ReplayError, StaleEpochError

def worker_provision(args):
    control,auth,i=args; c=DomainAuthorityAtomicCoordinator(control,auth); d=f"concurrent-{i}.keddeh"
    try: c.provision(f"tx-{i}",d,"KEDDEH_SYSTEMS",f"10.0.{i//250}.{i%250+1}"); return True
    except Exception as e: return repr(e)

def main():
    base=Path(tempfile.mkdtemp(prefix="keddah-r5-")); key=b"K"*32; results={}
    auth=SignedEnvelopeAuthority(base/"replay.sqlite3",key)
    env={"work_id":"WORK-R5-1","organisation_identity":"organisation://the-layna-company","operating_identity":"business-name://keddeh-systems","continuation":{"epoch":1},"state":{"action":"test"}}
    signed=auth.sign(env); auth.consume_once(signed); replay=False
    try: auth.consume_once(signed)
    except ReplayError: replay=True
    tampered=copy.deepcopy(signed); tampered["state"]["action"]="mutated"; tamper=False
    try: auth.verify(tampered)
    except IntegrityError: tamper=True
    results["signed_lineage"]={"first_consumed":True,"replay_rejected":replay,"tamper_rejected":tamper}
    e1=auth.acquire_lease("WORK-R5-LEASE","agent-A"); e2=auth.acquire_lease("WORK-R5-LEASE","agent-B"); stale=False
    try: auth.acquire_lease("WORK-R5-LEASE","agent-A-stale",requested_epoch=e1)
    except StaleEpochError: stale=True
    results["lease_fencing"]={"epoch_a":e1,"epoch_b":e2,"stale_epoch_rejected":stale,"current":auth.current_lease("WORK-R5-LEASE")}
    control=base/"control.sqlite3"; authority=base/"authority.sqlite3"; coord=DomainAuthorityAtomicCoordinator(control,authority); crash=[]
    for fp in ("after_control","after_authority"):
        domain=f"crash-{fp}.keddeh"; threw=False
        try: coord.provision("tx-"+fp,domain,"KEDDEH_SYSTEMS","127.0.0.1",failpoint=fp)
        except RuntimeError: threw=True
        obs=coord.observe(domain); crash.append({"failpoint":fp,"exception":threw,"control_absent":obs["control"] is None,"zone_absent":obs["zone"] is None,"records_absent":not obs["records"]})
    ok=coord.provision("tx-ok","atomic-ok.keddeh","KEDDEH_SYSTEMS","127.0.0.1"); obs=coord.observe("atomic-ok.keddeh"); results["crash_atomicity"]={"failures":crash,"success":ok,"success_observed":bool(obs["control"] and obs["zone"] and obs["records"])}
    tasks=[(str(control),str(authority),i) for i in range(200)]; t0=time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(8,os.cpu_count() or 2)) as ex: out=list(ex.map(worker_provision,tasks,chunksize=5))
    dt=time.perf_counter()-t0; failures=[x for x in out if x is not True]
    c=sqlite3.connect(control); n_control=c.execute("SELECT count(*) FROM domains WHERE domain LIKE 'concurrent-%'").fetchone()[0]; c.close(); a=sqlite3.connect(authority); n_zone=a.execute("SELECT count(*) FROM zones WHERE zone LIKE 'concurrent-%'").fetchone()[0]; a.close(); results["concurrent_writers"]={"attempts":200,"failures":len(failures),"control_rows":n_control,"authority_rows":n_zone,"seconds":dt,"tx_per_s":200/dt,"sample_failures":failures[:5]}
    cp=base/"checkpoint.json"; store=CheckpointStore(cp,key); root1=store.write({"work_id":"WORK-R5-CP","epoch":7,"holder":"agent-A","completed":["LEGAL","BRAINK"]}); child=base/"rehydrate_child.py"; child.write_text(f'''import sys,json\nsys.path.insert(0,{str(ROOT)!r})\nfrom enterprise.orchestration.durable_execution_r5 import CheckpointStore\ns=CheckpointStore({str(cp)!r},b"K"*32).read();s["epoch"]+=1;s["holder"]="agent-B";s["completed"].append("DOMAIN_AUTHORITY");print(json.dumps(s))\n'''); resumed=json.loads(subprocess.check_output([sys.executable,str(child)],text=True)); results["process_replacement"]={"checkpoint_root":root1,"resumed":resumed,"fresh_process":True,"identity_preserved":resumed["work_id"]=="WORK-R5-CP","epoch_advanced":resumed["epoch"]==8}
    wrapper=json.loads(cp.read_text()); wrapper["payload"]["epoch"]=999; cp.write_text(json.dumps(wrapper)); blocked=False
    try: store.read()
    except IntegrityError: blocked=True
    results["checkpoint_tamper"]={"rejected":blocked}
    checks={"replay_rejected":replay,"tamper_rejected":tamper,"stale_worker_fenced":stale,"crash_atomicity":all(x["control_absent"] and x["zone_absent"] and x["records_absent"] for x in crash),"successful_atomic_commit":results["crash_atomicity"]["success_observed"],"concurrent_writers_zero_failures":len(failures)==0 and n_control==200 and n_zone==200,"fresh_process_replacement":results["process_replacement"]["identity_preserved"] and results["process_replacement"]["epoch_advanced"],"checkpoint_tamper_rejected":blocked}
    report={"schema":"keddah.durable-execution.failure-suite.r5/v1","environment":{"python":sys.version,"cpu_count":os.cpu_count()},"results":results,"checks":checks,"all_passed":all(checks.values())}; print(json.dumps(report,indent=2))
if __name__=="__main__": main()
