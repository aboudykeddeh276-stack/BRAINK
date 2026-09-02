from pathlib import Path
import pytest
from system_evolution import *


def test_vfs_checkpoint_roundtrip(tmp_path):
    v=DeterministicVFS(); v.write('/a',{'x':1}); root=v.checkpoint(tmp_path/'cp.json')
    assert DeterministicVFS.restore(tmp_path/'cp.json').root()==root


def test_ledger_hash_chain(tmp_path):
    p=tmp_path/'l.ndjson'; l=ImmutableLedger(p); a=l.append('A','one',{}); b=l.append('B','two',{'x':1})
    assert b.prev_hash==a.event_hash and ImmutableLedger(p).head==b.event_hash


def test_orchestrator_and_cycle_rejection(tmp_path):
    l=ImmutableLedger(tmp_path/'l'); v=DeterministicVFS(); o=Orchestrator(l,v)
    o.register(ModuleContract('a',(),lambda _:{'n':1})); o.register(ModuleContract('b',('a',),lambda x:{'n':x['a']['n']+1}))
    assert o.run(['b'])['b']['n']==2
    c=Orchestrator(ImmutableLedger(tmp_path/'c'),DeterministicVFS()); c.register(ModuleContract('a',('b',),lambda _:{})); c.register(ModuleContract('b',('a',),lambda _:{}))
    with pytest.raises(ValueError): c.order(['a'])


def test_cognitive_refraction_majority():
    c=CognitiveRefraction(); c.register('a',lambda s:{'x':1}); c.register('b',lambda s:{'x':1}); c.register('c',lambda s:{'x':2})
    r=c.reconcile(c.run({})); assert r['promotion_allowed'] and r['agreement_count']==2


def test_promotion_stops_on_failure():
    p=PromotionPipeline()
    for name in p.ORDER: p.register(name,lambda state,n=name: GateResult(n,n!='security',{'gate':n}))
    r=p.run({}); assert not r['promoted'] and r['gates'][-1]['gate']=='security'


def test_market_gate():
    r=capability_score({'functional':1,'deterministic':1,'recoverable':1,'observable':1,'secure':.85,'deployable':1})
    assert r['market_ready'] and r['score']==.9775
