from itertools import combinations, permutations
from braink_runtime.tot_safety import ToTSafetyKernel, Vote, SafetyViolation
from braink_runtime.coordinate_directory import DistributedCoordinateDirectory
from braink_runtime.layer2_reconciler import Layer2Reconciler, DesiredManifestation, ObservedManifestation

def run():
    results=[]
    def record(name, passed, detail): results.append({'scenario':name,'status':'PASS' if passed else 'FAIL','detail':detail})
    def vote(k,t,members): return [Vote(x,k.epoch,t.digest()) for x in members]
    members=('A','B','C')
    for n in range(4):
        for subset in combinations(members,n):
            k=ToTSafetyKernel(members); t=k.propose(actor='A',command='X',payload={'subset':subset})
            try: k.commit(t,vote(k,t,subset)); actual='COMMIT'
            except SafetyViolation as e: actual=str(e)
            expected='COMMIT' if n>=2 else 'QUORUM_NOT_REACHED'
            record(f'quorum_subset_{"".join(subset) or "empty"}',actual==expected,{'expected':expected,'actual':actual})
    k=ToTSafetyKernel(members)
    t1=k.propose(actor='A',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://a'}); r1=k.commit(t1,vote(k,t1,('A','B')))
    t2=k.propose(actor='B',command='DIRECTORY_REGISTER',payload={'coordinate':'kex://b'}); r2=k.commit(t2,vote(k,t2,('B','C')))
    for order in permutations(((t1,r1),(t2,r2))):
        d=DistributedCoordinateDirectory(); names=[x[0].payload['coordinate'] for x in order]
        try:
            for t,r in order: d.apply(t,r)
            actual='APPLIED'
        except SafetyViolation as e: actual=str(e)
        expected='APPLIED' if names==['kex://a','kex://b'] else 'DIRECTORY_REPLAY_GAP'
        record('directory_order_'+','.join(names),actual==expected,{'expected':expected,'actual':actual})
    k=ToTSafetyKernel(members); old=k.propose(actor='A',command='X',payload={}); k.advance_epoch(2,('A','B'))
    try: k.commit(old,[Vote('A',1,old.digest()),Vote('B',1,old.digest())]); actual='COMMIT'
    except SafetyViolation as e: actual=str(e)
    record('stale_epoch_writer',actual=='STALE_OR_FUTURE_EPOCH',actual)
    k=ToTSafetyKernel(members); t=k.propose(actor='A',command='X',payload={}); object.__setattr__(t,'previous_root','tampered')
    try: k.commit(t,vote(k,t,('A','B'))); actual='COMMIT'
    except SafetyViolation as e: actual=str(e)
    record('previous_root_tamper',actual=='PREVIOUS_ROOT_MISMATCH',actual)
    k=ToTSafetyKernel(members)
    try: k.propose(actor='0',command='X',payload={}); actual='ACCEPT'
    except SafetyViolation as e: actual=str(e)
    record('zero_actor_address',actual=='ZERO_NOT_PERMITTED_AS_ADDRESS',actual)
    r=Layer2Reconciler(); desired={'m1':DesiredManifestation('m1','host://new',2)}; observed={'m1':ObservedManifestation('m1','host://old',1,'ATTACHED')}
    plan=r.plan(desired,observed); observed2={'m1':ObservedManifestation('m1','host://new',2,'ATTACHED')}
    record('reconciler_idempotence_after_apply',len(plan)==1 and r.plan(desired,observed2)==(),{'first_plan':[x.kind for x in plan],'second_plan':[]})
    return {'schema':'kex.report03.fault-injection.v1','total':len(results),'passed':sum(x['status']=='PASS' for x in results),'failed':sum(x['status']=='FAIL' for x in results),'results':results}
