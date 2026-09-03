from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer


def _ctx():
    return mp.get_context('fork')


def _crash_write(root: str, phase: str) -> None:
    computer = RecursiveComputer.restore(Path(root), record_restore=False)
    computer.state['phase'] = phase
    computer._persist('CRASH_INJECTION', crash_phase=phase)


def _run_crash(root: Path, phase: str, expected_exit: int) -> None:
    worker = _ctx().Process(target=_crash_write, args=(str(root), phase))
    worker.start()
    worker.join(20)
    assert not worker.is_alive()
    assert worker.exitcode == expected_exit


def test_prepare_only_death_rolls_back_native_r26_state(tmp_path: Path) -> None:
    root = tmp_path / 'A'
    computer = RecursiveComputer(computer_id='A', state_root=root)
    computer.write_state('stable', 297)
    before = computer.readback()

    _run_crash(root, 'AFTER_PREPARE', 91)

    restored = RecursiveComputer.restore(root, record_restore=False)
    assert restored.readback() == before
    assert restored.commit_coordinator.classify()['status'] == 'CONSISTENT'
    assert restored.ledger.verify()


def test_state_ahead_death_recovers_exact_native_receipt_and_continues(tmp_path: Path) -> None:
    root = tmp_path / 'A'
    computer = RecursiveComputer(computer_id='A', state_root=root)
    computer.write_memory('seed', 297)

    _run_crash(root, 'AFTER_STATE', 92)

    restored = RecursiveComputer.restore(root, record_restore=False)
    assert restored.readback()['state']['phase'] == 'AFTER_STATE'
    assert restored.commit_coordinator.classify()['status'] == 'CONSISTENT'
    assert restored.ledger.verify()

    child = restored.instantiate('B')
    child.write_state('phase', 'POST_RECOVERY_CHILD')
    tree = RecursiveComputer.restore_tree(root)
    assert tree.children['B'].readback()['state']['phase'] == 'POST_RECOVERY_CHILD'
    assert tree.children['B'].identity.lineage == ('A', 'B')
    assert tree.commit_coordinator.classify()['status'] == 'CONSISTENT'
    assert tree.children['B'].commit_coordinator.classify()['status'] == 'CONSISTENT'


def test_ledger_committed_death_retires_journal_and_continues(tmp_path: Path) -> None:
    root = tmp_path / 'A'
    computer = RecursiveComputer(computer_id='A', state_root=root)

    _run_crash(root, 'AFTER_LEDGER', 93)

    restored = RecursiveComputer.restore(root, record_restore=False)
    assert restored.readback()['state']['phase'] == 'AFTER_LEDGER'
    assert restored.commit_coordinator.classify()['status'] == 'CONSISTENT'
    assert restored.ledger.verify()
    restored.write_state('continued', True)
    assert RecursiveComputer.restore(root, record_restore=False).readback()['state']['continued'] is True


def test_unrelated_divergence_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / 'A'
    computer = RecursiveComputer(computer_id='A', state_root=root)
    computer.write_state('stable', 1)

    _run_crash(root, 'AFTER_PREPARE', 91)

    # Deliberately mutate committed state outside both the old and prepared values.
    (root / 'computer.json').write_text('{"constructor":"alien"}')

    try:
        RecursiveComputer.restore(root, record_restore=False)
    except RuntimeError as exc:
        assert 'R31_RECOVERY_BLOCKED' in str(exc)
    else:
        raise AssertionError('unrelated divergence must not be guessed away')
