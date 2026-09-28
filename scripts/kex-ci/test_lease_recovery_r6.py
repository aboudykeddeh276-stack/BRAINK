from pathlib import Path
import json, sys, tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from enterprise.orchestration.durable_execution_r5 import SignedEnvelopeAuthority
from enterprise.orchestration.lease_recovery_r6 import RecoverableLeaseAuthority, LeaseRecoveryError

def require(cond,msg):
    if not cond:
        raise AssertionError(msg)

def main():
    base=Path(tempfile.mkdtemp(prefix="braink-lease-r6-"))
    authority=SignedEnvelopeAuthority(base/"authority.sqlite3",b"K"*32)
    leases=RecoverableLeaseAuthority(authority)

    first=leases.acquire_lease("WORK-R6-RECOVER","agent-A",ttl_ns=100,max_retries=2,now_ns=1000)
    require(first["state"]=="LEASED","initial lease not active")
    extended=leases.heartbeat("WORK-R6-RECOVER","agent-A",first["epoch"],ttl_ns=200,now_ns=1050)
    require(extended["lease_expires_ns"]==1250,"heartbeat did not extend expiry")

    before=leases.reconcile_expired_leases(now_ns=1249)
    require(before["recovered_count"]==0,"lease recovered before expiry")
    recovered=leases.reconcile_expired_leases(now_ns=1251)
    require(recovered["recovered_work_ids"]==["WORK-R6-RECOVER"],"expired lease not recovered")
    state=leases.current_lease("WORK-R6-RECOVER")
    require(state["state"]=="RECOVERABLE","recovered lease not eligible")
    require(state["retry_count"]==1,"retry count not incremented")

    successor=leases.acquire_lease("WORK-R6-RECOVER","agent-B",ttl_ns=100,now_ns=1300)
    require(successor["epoch"]==first["epoch"]+1,"successor epoch not fenced")

    poison=leases.acquire_lease("WORK-R6-POISON","agent-X",ttl_ns=100,max_retries=0,now_ns=2000)
    poisoned=leases.reconcile_expired_leases(now_ns=2101)
    require(poisoned["poisoned_work_ids"]==["WORK-R6-POISON"],"retry-exhausted lease not poisoned")
    pstate=leases.current_lease("WORK-R6-POISON")
    require(pstate["state"]=="POISON_PILL_FAILED","poison state missing")
    failures=leases.failure_records("WORK-R6-POISON")
    require(len(failures)==1,"failure ledger row missing")
    require(failures[0]["disposition"]=="REMEDIATION_REQUIRED","failure not routed to remediation")

    stale=False
    try:
        leases.heartbeat("WORK-R6-RECOVER","agent-A",first["epoch"],ttl_ns=100,now_ns=1400)
    except LeaseRecoveryError:
        stale=True
    require(stale,"stale worker heartbeat accepted")

    report={
        "schema":"braink.lease-recovery.r6/v1",
        "checks":{
            "heartbeat_extends_lease":True,
            "expiry_requeues_work":True,
            "retry_count_increments":True,
            "successor_epoch_fenced":True,
            "retry_exhaustion_poisoned":True,
            "remediation_record_written":True,
            "stale_heartbeat_rejected":True
        },
        "all_passed":True
    }
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
