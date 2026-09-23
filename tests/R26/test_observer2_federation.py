from pathlib import Path
from enterprise.observer2_environment_federation import Observer2EnvironmentFederation,FileSystemProbe,ProcessProbe,RecursiveComputerProbe,AddressProbe
from enterprise.development_action_lane import DevelopmentActionLane


def test_federation_samples_distinct_environments(tmp_path: Path):
    (tmp_path/'x').write_text('1')
    fed=Observer2EnvironmentFederation([
        FileSystemProbe('filesystem',tmp_path,('x','missing')),
        ProcessProbe(),
        RecursiveComputerProbe('computer',lambda:{'state':'READY','lineage':['A']}),
        AddressProbe('address',lambda:{'logical':'computer://A','backing':'file://A/computer.json'}),
    ])
    s=fed.sample()
    assert s['environments']['filesystem']['paths']['x']['exists']
    assert not s['environments']['filesystem']['paths']['missing']['exists']
    assert s['environments']['computer']['state']['lineage']==['A']
    assert s['environments']['address']['resolved']
    assert s['environment_root']


def test_development_lane_has_no_sampling_api(tmp_path: Path):
    lane=DevelopmentActionLane(tmp_path/'lane.jsonl')
    assert not hasattr(lane,'observe')
    assert not hasattr(lane,'sample')
