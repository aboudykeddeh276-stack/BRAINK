from __future__ import annotations

from pathlib import Path
import json
import shutil

import pytest

from enterprise.resident_root_runtime import resolve_roots, require_resident_integrity
from modules.kex_core.canonical_state import CanonicalBoundary, mapping_adapter


def _fixture_tree(tmp_path: Path) -> Path:
    root = tmp_path / 'repo'
    required = [
        'enterprise/recursive_computer_runtime_r26.py',
        'enterprise/self_addressing_runtime.py',
        'enterprise/domain_authority_binding.py',
        'runtime/runtime_registry.py',
        'deployment/bootstrap_keddeh_fabric.py',
        'dependencies/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority/kex_dns.py',
        'dependencies/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority/kex_registrar_service.py',
    ]
    for rel in required:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('# fixture\n', encoding='utf-8')
    return root


def test_resident_roots_resolve_without_any_carrier_probe(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path)
    graph = resolve_roots(root)
    require_resident_integrity(graph)
    for rid in ('BRAINK_ROOT','DOMAIN_ROOT','DNS_ROOT','REGISTRAR_ROOT','SERVER_ROOT','CLOUD_ROOT'):
        assert graph['roots'][rid]['payload']['state'] == 'BOUND'
        assert graph['roots'][rid]['payload']['implementation_exists'] is True
        assert graph['roots'][rid]['stateDigest']
    assert graph['roots']['TLS_ROOT']['payload']['state'] == 'UNBOUND'
    assert graph['roots']['TLS_ROOT']['identity'] == 'LEX://BRAINK/TLS_ROOT'


def test_carrier_metadata_cannot_change_resident_graph_digest(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path)
    first = resolve_roots(root)
    # Create arbitrary carrier material outside the declared resident object graph.
    (root / 'carrier.json').write_text(json.dumps({'ip':'192.0.2.10','port':443}), encoding='utf-8')
    second = resolve_roots(root)
    assert first['graph_digest'] == second['graph_digest']
    assert first['roots']['BRAINK_ROOT']['stateDigest'] == second['roots']['BRAINK_ROOT']['stateDigest']


def test_broken_resident_binding_blocks_integrity(tmp_path: Path) -> None:
    root = _fixture_tree(tmp_path)
    (root / 'runtime/runtime_registry.py').unlink()
    graph = resolve_roots(root)
    assert graph['roots']['SERVER_ROOT']['payload']['state'] == 'BROKEN_BINDING'
    with pytest.raises(RuntimeError, match='RESIDENT_ROOT_BINDING_FAILURE'):
        require_resident_integrity(graph)


def test_canonical_root_roundtrip_preserves_identity() -> None:
    boundary = CanonicalBoundary()
    boundary.register(mapping_adapter('root'))
    state = boundary.enter(
        'root',
        {'root_id':'DOMAIN_ROOT','state':'BOUND'},
        identity='LEX://BRAINK/DOMAIN_ROOT',
        authority='BRAINK',
    )
    outward = boundary.exit('root', state)
    assert outward == {'root_id':'DOMAIN_ROOT','state':'BOUND'}
    assert boundary.evidence[-1].identity_preserved is True
