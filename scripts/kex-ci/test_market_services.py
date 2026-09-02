import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.market_services.service_broker import MarketServiceBroker,sha

with tempfile.TemporaryDirectory() as td:
    b=MarketServiceBroker(Path(td)/"broker.sqlite3")
    checks={}
    a=b.execute("agent_control","register_agent",{"agent_id":"agent://runtime/1","scope":"RUNTIME"})
    checks["agent_register"]=a["status"]=="PASS" and a["result"]["epoch"]==1
    auth=b.execute("agent_control","authorize_action",{"agent_id":"agent://runtime/1","required_scope":"RUNTIME","expected_epoch":1})
    checks["agent_authorize"]=auth["status"]=="PASS" and auth["result"]["decision"]=="ALLOW"
    stale=b.execute("agent_control","authorize_action",{"agent_id":"agent://runtime/1","required_scope":"RUNTIME","expected_epoch":0})
    checks["stale_rejected"]=stale["status"]=="REJECTED"
    run=b.execute("runtime_supervisor","create_run",{"run_id":"RUN-1"})
    b.execute("runtime_supervisor","checkpoint",{"run_id":"RUN-1","step":7,"checkpoint":"VFS://CP/7","continuation":"RESUME_8"})
    rh=b.execute("runtime_supervisor","rehydrate",{"run_id":"RUN-1"})
    checks["rehydration"]=rh["status"]=="PASS" and rh["result"]["state"]["step"]==7
    payload={"matter":"M-1","evidence":["A"]}
    hand=b.execute("handoff_guard","validate_handoff",{"payload":payload,"required_fields":["matter","evidence"],"referent":"M-1","expected_referent":"M-1","expected_digest":sha(payload),"recipient_capabilities":["READ_EVIDENCE"],"required_capabilities":["READ_EVIDENCE"]})
    checks["handoff_pass"]=hand["status"]=="PASS"
    fin=b.execute("ai_finops","measure_run",{"cost":19.82,"successful_tasks":183,"failed_tasks":17,"p95_latency_ms":4200})
    checks["finops"]=fin["status"]=="PASS" and round(fin["result"]["cost_per_success"],4)==round(19.82/183,4)
    audit=b.execute("proof_service","export_audit_pack",{})
    checks["audit_root"]=audit["status"]=="PASS" and len(audit["result"]["audit_root"])==64
    checks["all_have_hr_groups"]=all(len(x["hr_groups"])==5 for x in [a,auth,stale,run,rh,hand,fin,audit])
    print(json.dumps({"checks":checks},indent=2))
    raise SystemExit(0 if all(checks.values()) else 2)
