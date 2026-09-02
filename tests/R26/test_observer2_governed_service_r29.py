from deployment.recursive_computer_service_r29 import GovernedRuntimeHost
from enterprise.observer2_runtime import Observer2Runtime
from enterprise.observer2_environment_federation import Observer2EnvironmentFederation,ProcessProbe

def test_sampling_clock_does_not_fake_environment_change():
    observer=Observer2Runtime('OBSERVER2://TEST',{},federation=Observer2EnvironmentFederation([ProcessProbe()]))
    pre=observer.sample('PRE'); post=observer.sample('POST')
    assert observer.compare(pre,post)['changed'] is False

def test_default_service_state_write_is_observer2_governed(tmp_path):
    host=GovernedRuntimeHost(tmp_path/'A','A')
    out=host.write_state('A','observer2_invoked',297)
    assert out['state']['observer2_invoked']==297
    assert out['observer2_governance']['pre']['environment']['kind']=='FEDERATED'
    assert out['observer2_governance']['post']['environment']['kind']=='FEDERATED'
    assert out['observer2_governance']['continuation']=='FOLLOW_SUCCESSOR_STATE'
    assert out['ledger_verified']

def test_default_service_constructor_is_observer2_governed(tmp_path):
    host=GovernedRuntimeHost(tmp_path/'A','A')
    out=host.instantiate('A','B')
    assert out['lineage']==['A','B']
    assert out['observer2_governance']['continuation']=='FOLLOW_SUCCESSOR_STATE'
    parent=host.snapshot(host.resolve('A'))
    assert 'B' in parent['children']
    assert parent['ledger_verified']
