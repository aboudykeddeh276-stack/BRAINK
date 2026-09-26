from pathlib import Path
from enterprise.system_contract_registry import SystemContractRegistry
from deployment.kex_runtime_service_r35 import RuntimeHost

ROOT=Path(__file__).resolve().parents[2]

def test_system_graph_has_distinct_classes_and_complete_contracts():
    registry=SystemContractRegistry(ROOT/'control'/'SYSTEM_INTERFACE_GRAPH_R35.json')
    out=registry.verify()
    assert out['status']=='VERIFIED'
    assert out['component_count'] >= 6
    assert 'runtime://kex/runtime' in out['authorities']
    assert 'authority://illlm/keddeh' in out['authorities']
    assert 'authority://kex/dns' in out['authorities']
    assert 'authority://kex/registrar' in out['authorities']

def test_readiness_is_gated_by_system_contract_graph(tmp_path):
    host=RuntimeHost(tmp_path/'A','A')
    ready=host.ready()
    assert ready['status']=='READY'
    assert ready['ledger_verified'] is True
    assert ready['system_graph_verified'] is True
    assert ready['component_count'] >= 6
