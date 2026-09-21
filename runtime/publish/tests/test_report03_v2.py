import os, tempfile
import pytest
from braink_runtime.tot_safety import ToTSafetyKernel, SafetyViolation
from braink_runtime.coordinate_directory import DistributedCoordinateDirectory
from braink_runtime.layer2_reconciler import Layer2Reconciler, DesiredManifestation, ObservedManifestation
from braink_runtime.evidence_journal import EvidenceJournal, JournalViolation

MEMBERS=['A','B','C']
def qvotes(k,t,*members): return [k.vote(m,t) for m in members]
def commit(k, actor, command, payload, voters=('A','B')):
    t=k.propose(actor=actor,command=command,payload=payload); return t,k.commit(t,qvotes(k,t,*voters))

def test_tot_chain_roundtrip():
    k=ToTSafetyKernel(MEMBERS); ts=[]; rs=[]
    for n in range(3):
        t,r=commit(k,'A','X',{'n':n}); ts.append(t); rs.append(r)
    assert ToTSafetyKernel.verify_chain(MEMBERS,ts,rs)==k.root
    assert ToTSafetyKernel.recover(MEMBERS,ts,rs).root==k.root

def test_tot_chain_rejects_reordered_receipts():
    k=ToTSafetyKernel(MEMBERS); t1,r1=commit(k,'A','X',{'n':1}); t2,r2=commit(k,'A','X',{'n':2})
    with pytest.raises(SafetyViolation): ToTSafetyKernel.verify_chain(MEMBERS,[t1,t2],[r2,r1])

def test_tot_quorum_fails_closed():
    k=ToTSafetyKernel(MEMBERS); t=k.propose(actor='A',command='X',payload={})
    with pytest.raises(SafetyViolation,match='QUORUM_NOT_REACHED'): k.commit(t,[k.vote('A',t)])

def test_tot_equivocation_rejected():
    k=ToTSafetyKernel(MEMBERS); l=k.propose(actor='A',command='X',payload={'v':'L'}); r=k.propose(actor='B',command='X',payload={'v':'R'})
    k.vote('B',l)
    with pytest.raises(SafetyViolation,match='VOTER_EQUIVOCATION'): k.vote('B',r)

def test_membership_change_explicitly_unimplemented():
    k=ToTSafetyKernel(MEMBERS)
    with pytest.raises(SafetyViolation,match='MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED'): k.reconfigure_membership(['A','B','C','D'])

def test_evidence_journal_append_recover_and_tamper():
    with tempfile.TemporaryDirectory() as td:
        p=os.path.join(td,'e.jsonl'); j=EvidenceJournal(p); j.append('A',{'x':1}); j.append('B',{'x':2})
        assert len(j.recover())==2
        raw=open(p,'rb').read().replace(b'"x":2',b'"x":9'); open(p,'wb').write(raw)
        with pytest.raises(JournalViolation,match='JOURNAL_HASH_MISMATCH'): j.recover()

def test_evidence_journal_partial_tail_recovery():
    with tempfile.TemporaryDirectory() as td:
        p=os.path.join(td,'e.jsonl'); j=EvidenceJournal(p); j.append('A',{'x':1})
        with open(p,'ab') as f: f.write(b'{"partial":')
        with pytest.raises(JournalViolation,match='PARTIAL_TAIL_RECORD'): j.recover()
        assert len(j.recover(truncate_partial_tail=True))==1
        assert open(p,'rb').read().endswith(b'\n')

def test_directory_replica_sync_and_snapshot_restore():
    k=ToTSafetyKernel(MEMBERS); a=DistributedCoordinateDirectory(MEMBERS); b=DistributedCoordinateDirectory(MEMBERS)
    t1,r1=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://alpha'}); a.apply(t1,r1)
    t2,r2=commit(k,'B','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://alpha','manifestation_id':'m1','endpoint':'host://one','generation':2,'state':'ATTACHED'},('B','C')); a.apply(t2,r2)
    assert b.sync_from(a)==2 and b.directory_root()==a.directory_root()
    restored=DistributedCoordinateDirectory.from_snapshot(a.snapshot(),MEMBERS)
    assert restored.directory_root()==a.directory_root() and restored.applied_index==2

def test_directory_snapshot_tamper_rejected():
    k=ToTSafetyKernel(MEMBERS); d=DistributedCoordinateDirectory(MEMBERS)
    t,r=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://a'}); d.apply(t,r); snap=d.snapshot(); snap['records']['kex://a']['generation']=999
    with pytest.raises(SafetyViolation,match='DIRECTORY_SNAPSHOT_ROOT_MISMATCH'): DistributedCoordinateDirectory.from_snapshot(snap,MEMBERS)

def test_directory_zero_stale_and_gap_rejected():
    k=ToTSafetyKernel(MEMBERS); d=DistributedCoordinateDirectory(MEMBERS)
    t1,r1=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://a'}); t2,r2=commit(k,'A','DIRECTORY_REGISTER',{'coordinate':'kex://b'})
    with pytest.raises(SafetyViolation,match='DIRECTORY_REPLAY_GAP'): d.apply(t2,r2)
    d.apply(t1,r1); d.apply(t2,r2)
    t3,r3=commit(k,'A','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://a','manifestation_id':'m1','endpoint':'host://one','generation':3,'state':'ATTACHED'}); d.apply(t3,r3)
    t4,r4=commit(k,'A','DIRECTORY_UPSERT_MANIFESTATION',{'coordinate':'kex://a','manifestation_id':'m1','endpoint':'host://old','generation':3,'state':'ATTACHED'})
    with pytest.raises(SafetyViolation,match='STALE_GENERATION'): d.apply(t4,r4)
    kz=ToTSafetyKernel(MEMBERS); tz,rz=commit(kz,'A','DIRECTORY_REGISTER',{'coordinate':'0'}); dz=DistributedCoordinateDirectory(MEMBERS)
    with pytest.raises(SafetyViolation,match='ZERO_NOT_PERMITTED_AS_ADDRESS'): dz.apply(tz,rz)

class FakeActuator:
    def __init__(self, fail_once=None, corrupt=None, apply_then_fail=None): self.seen={}; self.fail_once=fail_once; self.failed=set(); self.corrupt=corrupt; self.apply_then_fail=apply_then_fail
    def execute(self,a,key):
        if key in self.seen: return self.seen[key]
        state='DETACHED' if a.kind=='DETACH' else 'ATTACHED'; o=ObservedManifestation(a.manifestation_id,a.endpoint,a.generation,state)
        if self.corrupt=='generation': o=ObservedManifestation(a.manifestation_id,a.endpoint,a.generation+1,state)
        if self.corrupt=='endpoint': o=ObservedManifestation(a.manifestation_id,'host://wrong',a.generation,state)
        if self.apply_then_fail==a.manifestation_id and a.manifestation_id not in self.failed:
            self.seen[key]=o; self.failed.add(a.manifestation_id); raise TimeoutError('response lost after side effect')
        if self.fail_once==a.manifestation_id and a.manifestation_id not in self.failed:
            self.failed.add(a.manifestation_id); raise RuntimeError('injected actuator failure')
        self.seen[key]=o; return o

def test_l2_success_idempotence_detach():
    r=Layer2Reconciler(); act=FakeActuator(); desired={'m1':DesiredManifestation('m1','host://new',2)}; observed={'m1':ObservedManifestation('m1','host://old',1,'ATTACHED'),'m2':ObservedManifestation('m2','host://extra',1,'ATTACHED')}
    after,receipt=r.reconcile_once(desired,observed,act); assert receipt.status=='PASS' and receipt.converged
    after2,receipt2=r.reconcile_once(desired,after,act); assert receipt2.action_receipts==() and receipt2.converged and after2==after

def test_l2_partial_failure_retry_converges():
    r=Layer2Reconciler(); act=FakeActuator(fail_once='m2'); desired={'m1':DesiredManifestation('m1','host://new',2),'m2':DesiredManifestation('m2','host://two',1)}
    partial,receipt=r.reconcile_once(desired,{},act); assert receipt.status=='PARTIAL_FAILURE' and len(partial)==1
    final,receipt2=r.reconcile_once(desired,partial,act); assert receipt2.status=='PASS' and receipt2.converged

def test_l2_ambiguous_apply_then_timeout_recovers_with_idempotency_key():
    r=Layer2Reconciler(); act=FakeActuator(apply_then_fail='m1'); desired={'m1':DesiredManifestation('m1','host://one',1)}
    partial,receipt=r.reconcile_once(desired,{},act); assert receipt.status=='PARTIAL_FAILURE' and partial=={}
    final,receipt2=r.reconcile_once(desired,partial,act); assert receipt2.status=='PASS' and receipt2.converged and final['m1'].endpoint=='host://one'

def test_l2_rejects_corrupt_actuator_generation():
    r=Layer2Reconciler(); act=FakeActuator(corrupt='generation'); desired={'m1':DesiredManifestation('m1','host://one',1)}
    after,receipt=r.reconcile_once(desired,{},act); assert receipt.status=='PARTIAL_FAILURE' and after=={} and 'ACTUATOR_RESULT_GENERATION_MISMATCH' in receipt.action_receipts[0].error

def test_l2_rejects_corrupt_actuator_endpoint():
    r=Layer2Reconciler(); act=FakeActuator(corrupt='endpoint'); desired={'m1':DesiredManifestation('m1','host://one',1)}
    after,receipt=r.reconcile_once(desired,{},act); assert receipt.status=='PARTIAL_FAILURE' and after=={} and 'ACTUATOR_RESULT_ENDPOINT_MISMATCH' in receipt.action_receipts[0].error

def test_l2_future_generation_rejected():
    r=Layer2Reconciler(); desired={'m1':DesiredManifestation('m1','host://one',2)}; observed={'m1':ObservedManifestation('m1','host://one',3,'ATTACHED')}
    with pytest.raises(SafetyViolation,match='OBSERVED_GENERATION_AHEAD'): r.plan(desired,observed)
