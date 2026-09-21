import tempfile, threading
from pathlib import Path
import pytest
from dataclasses import asdict
from braink_runtime.report03_mesh import *

def start(tmp,name,members=('A','B','C'),secret='s'):
    st=DurablePaxosToT(name,members,Path(tmp)/f'{name}.wal',secret)
    srv=Server(('127.0.0.1',0),st);th=threading.Thread(target=srv.serve_forever,daemon=True);th.start()
    return st,srv,f'127.0.0.1:{srv.server_address[1]}'

def stop(s):s.shutdown();s.server_close()

def cluster(tmp,members=('A','B','C'),extra=()):
    nodes={n:start(tmp,n,members) for n in tuple(members)+tuple(extra)};eps={n:v[2] for n,v in nodes.items()};return nodes,Coordinator(eps,'s')

def test_basic_commit_directory_and_barrier():
    with tempfile.TemporaryDirectory() as td:
        nodes,c=cluster(td)
        c.propose_commit('A','DIRECTORY_REGISTER',{'coordinate':'L1'})
        c.propose_commit('A','DIRECTORY_UPSERT',{'coordinate':'L1','manifestation_id':'M1','endpoint':'tcp://m1','generation':1})
        r,p=c.barrier_read('A','L1');assert r['manifestations']['M1']['endpoint']=='tcp://m1';assert p['index']==3
        [stop(x[1]) for x in nodes.values()]

def test_minority_orphan_acceptance_is_adopted_and_completed():
    with tempfile.TemporaryDirectory() as td:
        nodes,c=cluster(td);pc=Client('s');states=c.live_states();base=states['A'];idx=1;ballot=1
        pre={'op':'PREPARE','index':idx,'epoch':1,'ballot':ballot,'previous_root':base['root'],'config_hash':base['config_hash']}
        # Only A promises/accepts X: no quorum/commit.
        assert pc.call(nodes['A'][2],pre)['ok']
        tx=Transition(idx,1,ballot,'A','BARRIER',{'orphan':'X'},base['root'],base['config_hash'])
        assert pc.call(nodes['A'][2],{'op':'ACCEPT','transition':asdict(tx)})['ok']
        # A later normal proposal for Y must first complete X, then commit Y at index 2.
        ry,_=c.propose_commit('A','BARRIER',{'requested':'Y'})
        assert ry.transition.index==2 and ry.transition.payload=={'requested':'Y'}
        for n in nodes:
            st=c.c.call(nodes[n][2],{'op':'STATE'});assert st['index']==2
        [stop(x[1]) for x in nodes.values()]

def test_same_ballot_conflict_rejected():
    with tempfile.TemporaryDirectory() as td:
        nodes,c=cluster(td);pc=Client('s');st=c.live_states()['A'];pre={'op':'PREPARE','index':1,'epoch':1,'ballot':7,'previous_root':st['root'],'config_hash':st['config_hash']}
        assert pc.call(nodes['A'][2],pre)['ok'];t1=Transition(1,1,7,'A','BARRIER',{'x':1},st['root'],st['config_hash']);t2=Transition(1,1,7,'A','BARRIER',{'x':2},st['root'],st['config_hash'])
        assert pc.call(nodes['A'][2],{'op':'ACCEPT','transition':asdict(t1)})['ok'];r=pc.call(nodes['A'][2],{'op':'ACCEPT','transition':asdict(t2)});assert not r['ok'] and 'SAME_BALLOT_EQUIVOCATION' in r['error']
        [stop(x[1]) for x in nodes.values()]

def test_restart_recovers_promise_and_acceptance():
    with tempfile.TemporaryDirectory() as td:
        st,srv,ep=start(td,'A');pc=Client('s');s=pc.call(ep,{'op':'STATE'});pre={'op':'PREPARE','index':1,'epoch':1,'ballot':9,'previous_root':s['root'],'config_hash':s['config_hash']};pc.call(ep,pre)
        t=Transition(1,1,9,'A','BARRIER',{'z':1},s['root'],s['config_hash']);pc.call(ep,{'op':'ACCEPT','transition':asdict(t)});stop(srv)
        st2,srv2,ep2=start(td,'A');s2=Client('s').call(ep2,{'op':'STATE'});assert s2['max_promised']==9
        p=Client('s').call(ep2,{'op':'PREPARE','index':1,'epoch':1,'ballot':10,'previous_root':s2['root'],'config_hash':s2['config_hash']});assert p['promise']['accepted']['transition']['payload']=={'z':1}
        stop(srv2)

def test_joint_membership_and_new_config_progress():
    with tempfile.TemporaryDirectory() as td:
        old=('A','B','C');new=('A','B','D');nodes,c=cluster(td,old,('D',))
        # D starts on old config but is standby until begin is committed.
        c.propose_commit('A','BEGIN_RECONFIG',{'new_members':list(new)})
        final,comm=c.propose_commit('A','FINALIZE_RECONFIG',{})
        assert len(set(comm)&set(old))>=2 and len(set(comm)&set(new))>=2
        post,comm2=c.propose_commit('A','BARRIER',{'after':1});assert post.transition.epoch==2
        [stop(x[1]) for x in nodes.values()]

def test_tamper_and_auth_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        nodes,c=cluster(td);r,_=c.propose_commit('A','BARRIER',{})
        bad=asdict(r);bad['receipt_hash']='0'*64;resp=Client('s').call(nodes['C'][2],{'op':'COMMIT','receipt':bad});assert not resp['ok'] and 'RECEIPT_HASH_MISMATCH' in resp['error']
        auth=Client('wrong').call(nodes['A'][2],{'op':'STATE'});assert not auth['ok'] and 'AUTHENTICATION_FAILED' in auth['error']
        [stop(x[1]) for x in nodes.values()]

def test_l2_actuator_boundary():
    a=LinuxBridgeActuator();cap=a.capability()
    if cap['ready']:pytest.skip('privileged iproute2 environment; destructive bridge mutation deliberately not run')
    with pytest.raises(SafetyViolation,match='LINUX_BRIDGE_ACTUATOR_UNAVAILABLE'):a.execute('ENSURE_BRIDGE','kex-test-br0')