from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer


def _attempt_state(obj: RecursiveComputer, key: str, value: int) -> str:
    try:
        obj.write_state(key, value)
        return "OK"
    except RuntimeError as exc:
        return str(exc)


def _attempt_child(obj: RecursiveComputer, child_id: str) -> str:
    try:
        obj.instantiate(child_id)
        return "OK"
    except (RuntimeError, ValueError) as exc:
        return f"{type(exc).__name__}:{exc}"


def test_stale_restored_writer_is_rejected_and_rolled_back(tmp_path: Path) -> None:
    root = tmp_path / "A"
    base = RecursiveComputer(computer_id="A", state_root=root)
    base.write_state("base", 1)
    left = RecursiveComputer.restore(root)
    right = RecursiveComputer.restore(root)

    with ThreadPoolExecutor(max_workers=2) as pool:
        left_result, right_result = pool.map(
            lambda args: _attempt_state(*args),
            [(left, "left", 297), (right, "right", 88)],
        )

    results = {left_result, right_result}
    assert "OK" in results
    assert "STALE_STATE_CONFLICT" in results

    committed = RecursiveComputer.restore(root).readback()["state"]
    assert committed["base"] == 1
    assert ("left" in committed) ^ ("right" in committed)
    loser = right if right_result == "STALE_STATE_CONFLICT" else left
    assert loser.state == {"base": 1}


def test_independent_restored_parents_admit_distinct_children(tmp_path: Path) -> None:
    root = tmp_path / "A"
    base = RecursiveComputer(computer_id="A", state_root=root)
    base.write_state("base", 1)
    left = RecursiveComputer.restore(root)
    right = RecursiveComputer.restore(root)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda args: _attempt_child(*args),
            [(left, "X"), (right, "Y")],
        ))

    assert results.count("OK") == 2
    restored = RecursiveComputer.restore_tree(root)
    assert sorted(restored.children) == ["X", "Y"]
    assert sorted(p.name for p in (root / "descendants").iterdir() if p.is_dir()) == ["X", "Y"]
    assert not (root / ".orphaned").exists()
    assert restored.ledger.verify()


def test_independent_restored_parents_serialize_same_child(tmp_path: Path) -> None:
    root = tmp_path / "A"
    base = RecursiveComputer(computer_id="A", state_root=root)
    base.write_state("base", 1)
    left = RecursiveComputer.restore(root)
    right = RecursiveComputer.restore(root)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda obj: _attempt_child(obj, "Z"),
            [left, right],
        ))

    assert results.count("OK") == 1
    assert sum(result == "ValueError:CHILD_ALREADY_EXISTS" for result in results) == 1
    restored = RecursiveComputer.restore_tree(root)
    assert sorted(restored.children) == ["Z"]
    assert sorted(p.name for p in (root / "descendants").iterdir() if p.is_dir()) == ["Z"]
    assert not (root / ".orphaned").exists()
    assert restored.ledger.verify()
