from __future__ import annotations
import json, random, sys
from dataclasses import asdict
from pathlib import Path
from braink_runtime.tot_safety import ToTSafetyKernel, SafetyViolation
from braink_runtime.coordinate_directory import DistributedCoordinateDirectory
from braink_runtime.layer2_reconciler import Layer2Reconciler, DesiredManifestation, ObservedManifestation

random.seed(297)
receipts=[]
def rec(name,status,detail): receipts.append({'scenario':name,'status':status,'detail':detail})
def expect_violation(name, token, fn):
    try: fn(); rec(name,'FAIL',{'expected':token,'observed':'NO_EXCEPTION'})
    except SafetyViolation as e: rec(name,'PASS' if token in str(e) else 'FAIL',{'expected':token,'observed':str(e)})
    except Exception as e: rec(name,'FAIL',{'expected':token,'observed':f'{type(e).__name__}:{e}'})

blocked=0; trials=500
for n in (3,5,7):
    members=[chr(65+i) for i in range(n)]; q=n//2+1
    for _ in range(trials//3):
        k=ToTSafetyKernel(members)
        left=k.propose(actor=members[0],command='X',payload={'b':'L'})
        right=k.propose(actor=members[1],command='X',payload={'b':'R'})
        lset=set(random.sample(members,q)); rset=set(random.sample(members,q))
        try:
            for v in lset: k.vote(v,left)
            for v in rset: k.vote(v,right)
        except SafetyViolation as e:
            if 'VOTER_EQUIVOCATION' in str(e): blocked+=1
rec('random_conflicting_quorums','PASS' if blocked==trials//3*3 else 'FAIL',{'trials':trials//3*3,'equivocation_blocks':blocked})

k=ToTSafetyKernel(['A','B','C']); t=k.propose(actor='A',command='X',payload={}); r=k.commit(t,[k.vote('A',t),k.vote('B',t)])
import copy
bad=copy.deepcopy(r); object.__setattr__(bad,'receipt_hash','0'*64)
expect_violation('tampered_receipt_hash','RECEIPT_HASH_MISMATCH',lambda:ToTSafetyKernel.verify_receipt(t,bad,['A','B','C']))
expect_violation('recovery_length_mismatch','RECOVERY_LENGTH_MISMATCH',lambda:ToTSafetyKernel.recover(['A','B','C'],[t],[]))

k=ToTSafetyKernel(['A','B','C']); a=DistributedCoordinateDirectory(['A','B','C']); b=DistributedCoordinateDirectory(['A','B','C'])
t1=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://alpha'}); r1=k.commit(t1,[k.vote('A',t1),k.vote('B',t1)]); a.apply(t1,r1); b.sync_from(a)
b.receipt_hash_by_index[1]='forged'
expect_violation('directory_replica_divergence','DIRECTORY_REPLICA_DIVERGENCE',lambda:b.sync_from(a))

k=ToTSafetyKernel(['A','B','C']); d=DistributedCoordinateDirectory(['A','B','C'])
def kc(actor,cmd,payload):
    t=k.propose(actor=actor,command=cmd,payload=payload); rr=k.commit(t,[k.vote('A',t),k.vote('B',t)]); return t,rr
for t0,r0 in [kc('A','DIRECTORY_REGISTER',{'coordinate':'kex://x'}),kc('A','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://x','manifestation_id':'m','endpoint':'host://1','generation':5,'state':'ATTACHED'})]: d.apply(t0,r0)
tbad,rbad=kc('A','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://x','manifestation_id':'m','endpoint':'host://old','generation':4,'state':'ATTACHED'})
expect_violation('directory_stale_generation','STALE_GENERATION',lambda:d.apply(tbad,rbad))

class FlakyActuator:
    def __init__(self,fail_probability=.25): self.fail_probability=fail_probability; self.seen={}
    def execute(self,a,key):
        if key in self.seen:return self.seen[key]
        if random.random()<self.fail_probability: raise RuntimeError('fault')
        state='DETACHED' if a.kind=='DETACH' else 'ATTACHED'
        o=ObservedManifestation(a.manifestation_id,a.endpoint,a.generation,state); self.seen[key]=o; return o

runs=100; converged=0; partials=0; exhausted=0
for _ in range(runs):
    rr=Layer2Reconciler(); act=FlakyActuator(.30)
    desired={f'm{j}':DesiredManifestation(f'm{j}',f'host://{j}',2) for j in range(4)}; observed={}
    for _round in range(12):
        observed,receipt=rr.reconcile_once(desired,observed,act)
        if receipt.status=='PARTIAL_FAILURE': partials+=1
        if receipt.converged: converged+=1; break
    else: exhausted+=1
rec('l2_transient_fault_convergence','PASS' if converged==runs else 'FAIL',{'runs':runs,'converged':converged,'exhausted':exhausted,'partial_failure_receipts':partials})

class DeadActuator:
    def execute(self,a,key): raise RuntimeError('persistent fault')
rr=Layer2Reconciler(); observed,receipt=rr.reconcile_once({'m':DesiredManifestation('m','host://dead',1)}, {}, DeadActuator())
rec('l2_persistent_fault_fail_closed','PASS' if receipt.status=='PARTIAL_FAILURE' and not receipt.converged else 'FAIL',{'status':receipt.status,'converged':receipt.converged,'action_receipts':[asdict(x) for x in receipt.action_receipts]})
k=ToTSafetyKernel(['A','B','C'])
expect_violation('membership_change_not_implemented','MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED',lambda:k.reconfigure_membership(['A','B','C','D']))

summary={'seed':297,'scenarios':len(receipts),'passed':sum(x['status']=='PASS' for x in receipts),'failed':sum(x['status']=='FAIL' for x in receipts),'receipts':receipts}
print(json.dumps(summary,indent=2))
raise SystemExit(1 if summary['failed'] else 0)
