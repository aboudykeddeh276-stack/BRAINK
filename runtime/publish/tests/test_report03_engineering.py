import pytest
from braink_runtime.tot_safety import ToTSafetyKernel, Vote, SafetyViolation
from braink_runtime.coordinate_directory import DistributedCoordinateDirectory
from braink_runtime.layer2_reconciler import Layer2Reconciler, DesiredManifestation, ObservedManifestation, Action

def votes(k,t,*members): return [Vote(m,k.epoch,t.digest()) for m in members]

def test_kernel_commit_and_replay():
    k=ToTSafetyKernel(['A','B','C'])
    t=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://alpha'})
    r=k.commit(t,votes(k,t,'A','B'))
    assert r.index==1 and k.replay_root()==k.root

def test_quorum_and_stale_epoch_falsifiers():
    k=ToTSafetyKernel(['A','B','C'])
    t=k.propose(actor='A',command='X',payload={})
    with pytest.raises(SafetyViolation,match='QUORUM_NOT_REACHED'): k.commit(t,votes(k,t,'A'))
    k.advance_epoch(2,['A','B'])
    with pytest.raises(SafetyViolation,match='STALE_OR_FUTURE_EPOCH'): k.commit(t,votes(k,t,'A','B'))

def test_conflicting_history_and_root_falsifier():
    k=ToTSafetyKernel(['A','B','C'])
    t=k.propose(actor='A',command='X',payload={'v':1}); k.commit(t,votes(k,t,'A','B'))
    bad=k.propose(actor='B',command='Y',payload={'v':2})
    object.__setattr__(bad,'previous_root','bad')
    with pytest.raises(SafetyViolation,match='PREVIOUS_ROOT_MISMATCH'): k.commit(bad,votes(k,bad,'A','B'))

def test_directory_only_accepts_committed_prefix_and_replay_determinism():
    k=ToTSafetyKernel(['A','B','C']); d=DistributedCoordinateDirectory()
    t1=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://alpha'}); r1=k.commit(t1,votes(k,t1,'A','B')); d.apply(t1,r1)
    t2=k.propose(actor='B',command='DIRECTORY_UPSERT_MANIFESTATION',payload={'coordinate':'kex://alpha','manifestation_id':'m1','endpoint':'host://one','generation':2,'state':'ATTACHED'}); r2=k.commit(t2,votes(k,t2,'B','C')); d.apply(t2,r2)
    d2=DistributedCoordinateDirectory(); d2.apply(t1,r1); d2.apply(t2,r2)
    assert d.directory_root()==d2.directory_root()

def test_directory_stale_generation_rejected():
    k=ToTSafetyKernel(['A','B','C']); d=DistributedCoordinateDirectory()
    t1=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://alpha'}); r1=k.commit(t1,votes(k,t1,'A','B')); d.apply(t1,r1)
    t2=k.propose(actor='A',command='DIRECTORY_UPSERT_MANIFESTATION',payload={'coordinate':'kex://alpha','manifestation_id':'m1','endpoint':'host://one','generation':3,'state':'ATTACHED'}); r2=k.commit(t2,votes(k,t2,'A','B')); d.apply(t2,r2)
    t3=k.propose(actor='A',command='DIRECTORY_UPSERT_MANIFESTATION',payload={'coordinate':'kex://alpha','manifestation_id':'m1','endpoint':'host://old','generation':2,'state':'ATTACHED'}); r3=k.commit(t3,votes(k,t3,'A','B'))
    with pytest.raises(SafetyViolation,match='STALE_GENERATION'): d.apply(t3,r3)

def test_reconciler_idempotence_replace_detach():
    r=Layer2Reconciler()
    desired={'m1':DesiredManifestation('m1','host://new',2)}
    observed={'m1':ObservedManifestation('m1','host://old',1,'ATTACHED'),'m2':ObservedManifestation('m2','host://extra',1,'ATTACHED')}
    p=r.plan(desired,observed)
    assert [x.kind for x in p]==['REPLACE','DETACH']
    converged={'m1':ObservedManifestation('m1','host://new',2,'ATTACHED')}
    assert r.plan(desired,converged)==()

def test_reconciler_rejects_observed_future_generation():
    r=Layer2Reconciler(); desired={'m1':DesiredManifestation('m1','host://one',2)}; observed={'m1':ObservedManifestation('m1','host://one',3,'ATTACHED')}
    with pytest.raises(SafetyViolation,match='OBSERVED_GENERATION_AHEAD'): r.plan(desired,observed)

def test_zero_only_as_assessment_not_address_state():
    k=ToTSafetyKernel(['A','B','C'])
    with pytest.raises(SafetyViolation,match='ZERO_NOT_PERMITTED_AS_ADDRESS'): k.propose(actor='0',command='X',payload={})
    t=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'0'}); rr=k.commit(t,votes(k,t,'A','B')); d=DistributedCoordinateDirectory()
    with pytest.raises(SafetyViolation,match='ZERO_NOT_PERMITTED_AS_ADDRESS'): d.apply(t,rr)

def test_duplicate_commit_delivery_rejected_by_index():
    k=ToTSafetyKernel(['A','B','C'])
    t=k.propose(actor='A',command='X',payload={'n':1}); k.commit(t,votes(k,t,'A','B'))
    with pytest.raises(SafetyViolation,match='NON_CONTIGUOUS_INDEX'): k.commit(t,votes(k,t,'A','B'))

def test_directory_replay_gap_rejected():
    k=ToTSafetyKernel(['A','B','C']); d=DistributedCoordinateDirectory()
    t1=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://a'}); r1=k.commit(t1,votes(k,t1,'A','B'))
    t2=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://b'}); r2=k.commit(t2,votes(k,t2,'A','B'))
    with pytest.raises(SafetyViolation,match='DIRECTORY_REPLAY_GAP'): d.apply(t2,r2)
    d.apply(t1,r1); d.apply(t2,r2)
    assert set(d.records)=={'kex://a','kex://b'}

def test_detach_preserves_coordinate_identity():
    k=ToTSafetyKernel(['A','B','C']); d=DistributedCoordinateDirectory()
    t1=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://a'}); r1=k.commit(t1,votes(k,t1,'A','B')); d.apply(t1,r1)
    t2=k.propose(actor='A',command='DIRECTORY_UPSERT_MANIFESTATION',payload={'coordinate':'kex://a','manifestation_id':'m1','endpoint':'host://one','generation':1,'state':'ATTACHED'}); r2=k.commit(t2,votes(k,t2,'A','B')); d.apply(t2,r2)
    t3=k.propose(actor='B',command='DIRECTORY_DETACH_MANIFESTATION',payload={'coordinate':'kex://a','manifestation_id':'m1','generation':2}); r3=k.commit(t3,votes(k,t3,'B','C')); d.apply(t3,r3)
    assert 'kex://a' in d.records and d.records['kex://a'].manifestations['m1'].state=='DETACHED'

def test_split_brain_attempt_cannot_form_two_quorums_with_same_membership():
    k=ToTSafetyKernel(['A','B','C'])
    t1=k.propose(actor='A',command='X',payload={'branch':'left'})
    t2=k.propose(actor='B',command='X',payload={'branch':'right'})
    k.commit(t1,votes(k,t1,'A','B'))
    with pytest.raises(SafetyViolation): k.commit(t2,votes(k,t2,'B','C'))

def test_rejoin_materialises_new_generation_after_detach():
    r=Layer2Reconciler()
    desired={'m1':DesiredManifestation('m1','host://new',4)}
    observed={'m1':ObservedManifestation('m1','host://old',3,'DETACHED')}
    assert r.plan(desired,observed)==(Action('REPLACE','m1','host://new',4),)
