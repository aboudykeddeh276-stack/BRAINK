import copy
import pytest
from braink_runtime.tot_safety import ToTSafetyKernel, SafetyViolation
from braink_runtime.coordinate_directory import DistributedCoordinateDirectory
from braink_runtime.layer2_reconciler import Layer2Reconciler, DesiredManifestation, ObservedManifestation

MEMBERS=['A','B','C']
def qvotes(k,t,*members): return [k.vote(m,t) for m in members]

def commit(k, actor, command, payload, voters=('A','B')):
    t=k.propose(actor=actor,command=command,payload=payload)
    return t,k.commit(t,qvotes(k,t,*voters))

def test_commit_receipt_recovery_and_replay():
    k=ToTSafetyKernel(MEMBERS)
    t,r=commit(k,'A','X',{'v':1})
    assert ToTSafetyKernel.verify_receipt(t,r,MEMBERS)
    recovered=ToTSafetyKernel.recover(MEMBERS,[t],[r])
    assert recovered.root==k.root==k.replay_root()

def test_voter_equivocation_is_rejected():
    k=ToTSafetyKernel(MEMBERS)
    left=k.propose(actor='A',command='X',payload={'branch':'left'})
    right=k.propose(actor='B',command='X',payload={'branch':'right'})
    k.vote('B',left)
    with pytest.raises(SafetyViolation,match='VOTER_EQUIVOCATION'): k.vote('B',right)

def test_tampered_quorum_certificate_is_rejected():
    k=ToTSafetyKernel(MEMBERS); t,r=commit(k,'A','X',{})
    bad=copy.deepcopy(r)
    object.__setattr__(bad.quorum_certificate,'certificate_hash','deadbeef')
    with pytest.raises(SafetyViolation,match='QUORUM_CERTIFICATE_HASH_MISMATCH'): ToTSafetyKernel.verify_receipt(t,bad,MEMBERS)

def test_unsupported_membership_change_fails_closed():
    k=ToTSafetyKernel(MEMBERS)
    with pytest.raises(SafetyViolation,match='MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED'): k.reconfigure_membership(['A','B','C','D'])

def test_directory_replica_sync_and_root_equality():
    k=ToTSafetyKernel(MEMBERS); a=DistributedCoordinateDirectory(MEMBERS); b=DistributedCoordinateDirectory(MEMBERS)
    t1,r1=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://alpha'}); a.apply(t1,r1)
    t2,r2=commit(k,'B','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://alpha','manifestation_id':'m1','endpoint':'host://one','generation':2,'state':'ATTACHED'},('B','C')); a.apply(t2,r2)
    assert b.sync_from(a)==2 and b.directory_root()==a.directory_root()

def test_directory_gap_stale_generation_and_zero_rejected():
    k=ToTSafetyKernel(MEMBERS); d=DistributedCoordinateDirectory(MEMBERS)
    t1,r1=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://a'})
    t2,r2=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://b'})
    with pytest.raises(SafetyViolation,match='DIRECTORY_REPLAY_GAP'): d.apply(t2,r2)
    d.apply(t1,r1); d.apply(t2,r2)
    t3,r3=commit(k,'A','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://a','manifestation_id':'m1','endpoint':'host://one','generation':3,'state':'ATTACHED'}); d.apply(t3,r3)
    t4,r4=commit(k,'A','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://a','manifestation_id':'m1','endpoint':'host://old','generation':3,'state':'ATTACHED'})
    with pytest.raises(SafetyViolation,match='STALE_GENERATION'): d.apply(t4,r4)
    kz=ToTSafetyKernel(MEMBERS); tz,rz=commit(kz,'A','DIRECTORY_REGISTER',{'coordinate':'0'}); dz=DistributedCoordinateDirectory(MEMBERS)
    with pytest.raises(SafetyViolation,match='ZERO_NOT_PERMITTED_AS_ADDRESS'): dz.apply(tz,rz)

def test_replica_divergence_is_detected():
    k=ToTSafetyKernel(MEMBERS); a=DistributedCoordinateDirectory(MEMBERS); b=DistributedCoordinateDirectory(MEMBERS)
    t,r=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://a'}); a.apply(t,r); b.apply(t,r)
    b.receipt_hash_by_index[1]='forged'
    with pytest.raises(SafetyViolation,match='DIRECTORY_REPLICA_DIVERGENCE'): b.sync_from(a)

class FakeActuator:
    def __init__(self, fail_once=None): self.seen={}; self.fail_once=fail_once; self.failed=set()
    def execute(self,a,key):
        if key in self.seen: return self.seen[key]
        if self.fail_once==a.manifestation_id and a.manifestation_id not in self.failed:
            self.failed.add(a.manifestation_id); raise RuntimeError('injected actuator failure')
        state='DETACHED' if a.kind=='DETACH' else 'ATTACHED'
        o=ObservedManifestation(a.manifestation_id,a.endpoint,a.generation,state); self.seen[key]=o; return o

def test_l2_success_idempotence_and_detach():
    r=Layer2Reconciler(); act=FakeActuator()
    desired={'m1':DesiredManifestation('m1','host://new',2)}
    observed={'m1':ObservedManifestation('m1','host://old',1,'ATTACHED'),'m2':ObservedManifestation('m2','host://extra',1,'ATTACHED')}
    after,receipt=r.reconcile_once(desired,observed,act)
    assert receipt.status=='PASS' and receipt.converged and r.converged(desired,after)
    again,receipt2=r.reconcile_once(desired,after,act)
    assert receipt2.action_receipts==() and receipt2.converged

def test_l2_partial_failure_is_receipted_and_retry_converges():
    r=Layer2Reconciler(); act=FakeActuator(fail_once='m2')
    desired={'m1':DesiredManifestation('m1','host://new',2),'m2':DesiredManifestation('m2','host://two',1)}
    observed={}
    partial,receipt=r.reconcile_once(desired,observed,act)
    assert receipt.status=='PARTIAL_FAILURE' and not receipt.converged and len(partial)==1
    final,receipt2=r.reconcile_once(desired,partial,act)
    assert receipt2.status=='PASS' and receipt2.converged and r.converged(desired,final)

def test_l2_future_generation_is_rejected():
    r=Layer2Reconciler(); desired={'m1':DesiredManifestation('m1','host://one',2)}; observed={'m1':ObservedManifestation('m1','host://one',3,'ATTACHED')}
    with pytest.raises(SafetyViolation,match='OBSERVED_GENERATION_AHEAD'): r.plan(desired,observed)
