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


def test_committed_inspection_does_not_amplify_runtime_observers(tmp_path: Path):
    root = RecursiveComputer(computer_id='A', state_root=tmp_path / 'A')
    root.write_memory('seed', 297)
    before_observers = len(root.runtime.observers)
    before_checkpoint = json.loads((tmp_path / 'A' / 'runtime-checkpoint.json').read_text())
    for _ in range(100):
        inspected = root.inspect_committed()
        assert inspected['value']['memory']['seed'] == 297
        assert inspected['ledger_verified']
    after_observers = len(root.runtime.observers)
    after_checkpoint = json.loads((tmp_path / 'A' / 'runtime-checkpoint.json').read_text())
    assert after_observers == before_observers
    assert after_checkpoint == before_checkpoint


def test_continuation_queue_coalesces_wakes_and_retires():
    from enterprise.continuation_runtime import ContinuationRuntime
    runtime = ContinuationRuntime()
    first = runtime.enqueue('KEX://REPAIR/A', 'process://repair', {'version': 1}, priority=1)
    second = runtime.enqueue('KEX://REPAIR/A', 'process://repair', {'version': 2}, priority=5)
    assert first.continuation_id == second.continuation_id
    assert len(runtime.queue) == 1
    assert second.payload == {'version': 2}
    assert second.priority == 5
    blocked = runtime.tick()
    assert blocked['status'] == 'BLOCKED'
    assert len(runtime.queue) == 1
    runtime.register_process('process://repair', lambda payload: {'status': 'COMMITTED', 'payload': payload})
    assert next(iter(runtime.queue.values())).state == 'READY'
    completed = runtime.tick()
    assert completed['status'] == 'COMPLETED'
    assert completed['retired'] is True
    assert runtime.queue == {}
    assert len(runtime.history) == 2
