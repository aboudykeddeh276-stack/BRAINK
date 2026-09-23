from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer


def _write_state_worker(root: str, key: str, value: int, queue) -> None:
    try:
        obj = RecursiveComputer.restore(Path(root))
        obj.write_state(key, value)
        queue.put((key, "OK"))
    except Exception as exc:
        queue.put((key, f"{type(exc).__name__}:{exc}"))


def _instantiate_worker(root: str, child_id: str, queue) -> None:
    try:
        obj = RecursiveComputer.restore(Path(root))
        obj.instantiate(child_id)
        queue.put((child_id, "OK"))
    except Exception as exc:
        queue.put((child_id, f"{type(exc).__name__}:{exc}"))


def _crash_mid_file_commit_worker(root: str) -> None:
    obj = RecursiveComputer.restore(Path(root))
    adapter = obj.runtime.registry.adapters["adapter://file/json"]

    def crash_before_replace(path: Path, raw: bytes) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os._exit(137)

    adapter._commit = crash_before_replace
    obj.write_state("must_not_commit", 999)


def _ctx():
    # fork is required here because the test deliberately kills workers with
    # os._exit and validates OS-level flock release semantics on POSIX hosts.
    return mp.get_context("fork")


def test_process_level_stale_writer_cas_fencing(tmp_path: Path) -> None:
    root = tmp_path / "A"
    base = RecursiveComputer(computer_id="A", state_root=root)
    base.write_state("base", 1)

    ctx = _ctx()
    q = ctx.Queue()
    workers = [
        ctx.Process(target=_write_state_worker, args=(str(root), "left", 297, q)),
        ctx.Process(target=_write_state_worker, args=(str(root), "right", 88, q)),
    ]
    for p in workers: p.start()
    for p in workers: p.join(20)
    assert all(not p.is_alive() for p in workers)

    results = dict(q.get(timeout=5) for _ in workers)
    assert list(results.values()).count("OK") == 1
    assert sum("STALE_STATE_CONFLICT" in result for result in results.values()) == 1

    restored = RecursiveComputer.restore(root)
    state = restored.readback()["state"]
    assert state["base"] == 1
    assert ("left" in state) ^ ("right" in state)
    assert restored.ledger.verify()


def test_process_level_constructor_serializes_same_child(tmp_path: Path) -> None:
    root = tmp_path / "A"
    RecursiveComputer(computer_id="A", state_root=root).write_state("base", 1)

    ctx = _ctx()
    q = ctx.Queue()
    workers = [ctx.Process(target=_instantiate_worker, args=(str(root), "Z", q)) for _ in range(2)]
    for p in workers: p.start()
    for p in workers: p.join(20)
    assert all(not p.is_alive() for p in workers)

    results = [q.get(timeout=5)[1] for _ in workers]
    assert results.count("OK") == 1
    assert sum("CHILD_ALREADY_EXISTS" in result for result in results) == 1

    restored = RecursiveComputer.restore_tree(root)
    assert sorted(restored.children) == ["Z"]
    assert restored.ledger.verify()
    assert not (root / ".orphaned").exists()


def test_process_level_constructor_admits_distinct_children(tmp_path: Path) -> None:
    root = tmp_path / "A"
    RecursiveComputer(computer_id="A", state_root=root).write_state("base", 1)

    ctx = _ctx()
    q = ctx.Queue()
    workers = [
        ctx.Process(target=_instantiate_worker, args=(str(root), "X", q)),
        ctx.Process(target=_instantiate_worker, args=(str(root), "Y", q)),
    ]
    for p in workers: p.start()
    for p in workers: p.join(20)
    assert all(not p.is_alive() for p in workers)

    results = dict(q.get(timeout=5) for _ in workers)
    assert results == {"X": "OK", "Y": "OK"}

    restored = RecursiveComputer.restore_tree(root)
    assert sorted(restored.children) == ["X", "Y"]
    assert restored.ledger.verify()
    assert not (root / ".orphaned").exists()


def test_killed_writer_before_replace_preserves_committed_state_and_recovers_lock(tmp_path: Path) -> None:
    root = tmp_path / "A"
    base = RecursiveComputer(computer_id="A", state_root=root)
    base.write_state("stable", 297)
    before = base.inspect_committed()

    ctx = _ctx()
    worker = ctx.Process(target=_crash_mid_file_commit_worker, args=(str(root),))
    worker.start()
    worker.join(20)
    assert not worker.is_alive()
    assert worker.exitcode == 137

    # The process died after fsync of computer.json.tmp but before os.replace.
    # The committed object must remain the old version and the dead process's
    # flock must have been released by the kernel.
    restored = RecursiveComputer.restore(root)
    after_crash = restored.inspect_committed()
    assert after_crash["value"]["state"] == {"stable": 297}
    assert after_crash["value_hash"] == before["value_hash"]
    assert restored.ledger.verify()
    assert (root / "computer.json.tmp").exists()

    # A subsequent normal write must overwrite/retire the stale temp object,
    # commit successfully, and remain warm-boot readable.
    restored.write_state("recovered", 88)
    assert not (root / "computer.json.tmp").exists()
    rehydrated = RecursiveComputer.restore(root)
    assert rehydrated.readback()["state"] == {"stable": 297, "recovered": 88}
    assert rehydrated.ledger.verify()
