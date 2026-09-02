from pathlib import Path
import json

import pytest

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer, execute_recursive_proof


def ledger_len(root: Path) -> int:
    path = root / 'ledger.json'
    return len(json.loads(path.read_text())) if path.exists() else 0


def test_recursive_proof_restored_and_executable(tmp_path: Path):
    proof = execute_recursive_proof(tmp_path)
    assert proof['status'] == 'VERIFIED'
    assert proof['lineage']['E'] == ['A', 'B', 'C', 'D', 'E']
    assert proof['memory']['E'] == {'child': 88, 'seed': 297}
    assert proof['tree'] == {'A': ['B'], 'B': ['C'], 'C': ['D'], 'D': ['E'], 'E': []}
    assert all(proof['ledger_verified'].values())


def test_child_id_cannot_escape_descendant_namespace(tmp_path: Path):
    root = RecursiveComputer(computer_id='A', state_root=tmp_path / 'A')
    outside = tmp_path / 'escape'
    for invalid in ('../escape', '../../escape', '.', '..', '/tmp/escape', 'A/B', ''):
        with pytest.raises(ValueError):
            root.instantiate(invalid)
    assert not outside.exists()
    assert root.readback()['children'] == []


def test_tree_restore_records_only_one_restore_event(tmp_path: Path):
    root = RecursiveComputer(computer_id='A', state_root=tmp_path / 'A')
    b = root.instantiate('B')
    b.instantiate('C')
    before = {
        'A': ledger_len(tmp_path / 'A'),
        'B': ledger_len(tmp_path / 'A' / 'descendants' / 'B'),
        'C': ledger_len(tmp_path / 'A' / 'descendants' / 'B' / 'descendants' / 'C'),
    }
    restored = RecursiveComputer.restore_tree(tmp_path / 'A')
    after = {
        'A': ledger_len(tmp_path / 'A'),
        'B': ledger_len(tmp_path / 'A' / 'descendants' / 'B'),
        'C': ledger_len(tmp_path / 'A' / 'descendants' / 'B' / 'descendants' / 'C'),
    }
    assert restored.children['B'].children['C'].identity.lineage == ('A', 'B', 'C')
    assert after['A'] == before['A'] + 1
    assert after['B'] == before['B']
    assert after['C'] == before['C']
