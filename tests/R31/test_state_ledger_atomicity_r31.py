from pathlib import Path
import subprocess, sys
import pytest
from enterprise.state_ledger_atomicity_r31 import StateLedgerAtomicityR31, durable_replace, read_json


def spawn_crash(root: Path, phase: str, payload: dict):
    code = f'''\nfrom enterprise.state_ledger_atomicity_r31 import StateLedgerAtomicityR31\nr=StateLedgerAtomicityR31({str(root)!r})\nr.commit("STATE_WRITE", {payload!r}, crash_phase={phase!r})\n'''
    return subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2])


def test_normal_commit_correspondence(tmp_path: Path):
    r=StateLedgerAtomicityR31(tmp_path/'A'); r.initialize({'phase':'BOOT'})
    out=r.commit('STATE_WRITE',{'phase':'READY','seed':297})
    assert out['status']=='COMMITTED'
    c=r.classify(); assert c['status']=='CONSISTENT'; assert c['ledger_events']==2
    assert r.inspect()['ledger'][-1]['commit_id']==r.inspect()['state']['commit_id']


@pytest.mark.parametrize('phase,exitcode,expected_repair',[
    ('AFTER_PREPARE',91,None),
    ('AFTER_STATE',92,'APPEND_PREPARED_LEDGER_EVENT'),
    ('AFTER_LEDGER',93,'FINALIZE_COMMITTED_TRANSACTION'),
])
def test_process_death_recovery(tmp_path: Path, phase: str, exitcode: int, expected_repair: str|None):
    root=tmp_path/'A'; r=StateLedgerAtomicityR31(root); r.initialize({'phase':'BOOT'})
    p=spawn_crash(root,phase,{'phase':phase,'seed':297})
    assert p.returncode==exitcode
    pre=r.classify()
    if phase=='AFTER_PREPARE': assert pre['status']=='CONSISTENT'
    elif phase=='AFTER_STATE': assert pre['status']=='STATE_AHEAD_OF_LEDGER'
    else: assert pre['status']=='CONSISTENT'
    rec=r.recover()
    if phase=='AFTER_PREPARE': assert rec['status']=='RECOVERED_ROLLBACK'
    else:
        assert rec['status']=='RECOVERED_COMMIT'; assert rec['repair']==expected_repair
    assert r.classify()['status']=='CONSISTENT'
    assert not r.journal_path.exists()


def test_ledger_ahead_replays_prepared_state(tmp_path: Path):
    root=tmp_path/'A'; r=StateLedgerAtomicityR31(root); r.initialize({'phase':'BOOT'})
    tx=r._prepared('STATE_WRITE',{'phase':'NEXT'})
    durable_replace(r.journal_path,tx)
    durable_replace(r.ledger_path,tx['previous_ledger']+[tx['next_event']])
    assert r.classify()['status']=='LEDGER_AHEAD_OF_STATE'
    rec=r.recover(); assert rec['repair']=='REPLAY_PREPARED_STATE'
    assert r.classify()['status']=='CONSISTENT'


def test_unrelated_divergence_fails_closed(tmp_path: Path):
    root=tmp_path/'A'; r=StateLedgerAtomicityR31(root); r.initialize({'phase':'BOOT'})
    tx=r._prepared('STATE_WRITE',{'phase':'NEXT'}); durable_replace(r.journal_path,tx)
    durable_replace(r.state_path,{'commit_id':'ALIEN','payload':{'phase':'CORRUPT'}})
    rec=r.recover(); assert rec['status']=='BLOCKED_UNRESOLVED_DIVERGENCE'
    assert r.journal_path.exists()


def test_ledger_payload_tamper_detected(tmp_path: Path):
    r=StateLedgerAtomicityR31(tmp_path/'A'); r.initialize({'phase':'BOOT'}); r.commit('STATE_WRITE',{'phase':'READY'})
    ledger=read_json(r.ledger_path); ledger[-1]['payload_hash']='0'*64; durable_replace(r.ledger_path,ledger)
    assert r.classify()['status']=='LEDGER_CORRUPTED'


def test_reorder_detected(tmp_path: Path):
    r=StateLedgerAtomicityR31(tmp_path/'A'); r.initialize({'phase':'BOOT'}); r.commit('STATE_WRITE',{'n':1}); r.commit('STATE_WRITE',{'n':2})
    ledger=read_json(r.ledger_path); ledger[1],ledger[2]=ledger[2],ledger[1]; durable_replace(r.ledger_path,ledger)
    assert r.classify()['status']=='LEDGER_CORRUPTED'


def test_post_recovery_successor_can_continue(tmp_path: Path):
    root=tmp_path/'A'; r=StateLedgerAtomicityR31(root); r.initialize({'phase':'BOOT'})
    p=spawn_crash(root,'AFTER_STATE',{'phase':'PARENT_INTERRUPTED'}); assert p.returncode==92
    assert r.recover()['status']=='RECOVERED_COMMIT'
    successor=StateLedgerAtomicityR31(root)
    out=successor.commit('SUCCESSOR_CREATED',{'phase':'DESCENDANT_READY','child':'B'})
    assert out['status']=='COMMITTED'; c=successor.classify(); assert c['status']=='CONSISTENT'; assert c['ledger_events']==3


def test_independent_processes_serialize_commits(tmp_path: Path):
    root=tmp_path/'A'; r=StateLedgerAtomicityR31(root); r.initialize({'phase':'BOOT'})
    procs=[]
    repo=Path(__file__).resolve().parents[2]
    for i in range(12):
        code=f'''\nfrom enterprise.state_ledger_atomicity_r31 import StateLedgerAtomicityR31\nr=StateLedgerAtomicityR31({str(root)!r})\nout=r.commit("PROCESS_WRITE",{{"writer":{i}}})\nassert out["status"]=="COMMITTED"\n'''
        procs.append(subprocess.Popen([sys.executable,'-c',code],cwd=repo))
    codes=[p.wait(timeout=20) for p in procs]
    assert codes==[0]*12
    c=r.classify(); assert c['status']=='CONSISTENT'; assert c['ledger_events']==13
    ledger=r.inspect()['ledger']; assert len({e['commit_id'] for e in ledger})==13
