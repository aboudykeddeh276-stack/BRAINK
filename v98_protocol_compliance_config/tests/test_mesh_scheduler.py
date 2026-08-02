from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_mesh_scheduler import (
    COMPLETED,
    PENDING,
    RUNNING,
    TIMED_OUT,
    DeterministicMeshScheduler,
    DuplicateWorkerError,
    InvalidTransitionError,
    run_mesh_scheduler_acceptance,
)


class MeshSchedulerTests(unittest.TestCase):
    def test_deterministic_allocation_capacity_and_completion(self) -> None:
        scheduler = DeterministicMeshScheduler()
        scheduler.register_worker("alpha", {"cpu", "network"}, 4)
        scheduler.register_worker("beta", {"cpu", "gpu"}, 4)
        scheduler.submit_task("network-task", {"cpu", "network"}, 2, priority=10)
        scheduler.submit_task("gpu-task", {"cpu", "gpu"}, 2, priority=5)

        allocations = scheduler.schedule()
        self.assertEqual(
            allocations,
            [
                {"task_id": "network-task", "worker_id": "alpha"},
                {"task_id": "gpu-task", "worker_id": "beta"},
            ],
        )
        self.assertEqual(scheduler.tasks["network-task"].state, RUNNING)
        scheduler.complete_task("network-task", {"ok": True})
        self.assertEqual(scheduler.tasks["network-task"].state, COMPLETED)
        self.assertEqual(scheduler.workers["alpha"].load, 0)

    def test_priority_and_stable_tie_breaking(self) -> None:
        scheduler = DeterministicMeshScheduler()
        scheduler.register_worker("alpha", {"cpu"}, 1)
        scheduler.register_worker("beta", {"cpu"}, 1)
        scheduler.submit_task("low", {"cpu"}, 1, priority=1)
        scheduler.submit_task("high", {"cpu"}, 1, priority=9)

        allocations = scheduler.schedule()
        self.assertEqual(allocations[0], {"task_id": "high", "worker_id": "alpha"})
        self.assertEqual(allocations[1], {"task_id": "low", "worker_id": "beta"})

    def test_capacity_deferral_and_timeout(self) -> None:
        scheduler = DeterministicMeshScheduler()
        scheduler.register_worker("alpha", {"cpu"}, 1)
        scheduler.submit_task("too-large", {"cpu"}, 2, deadline=3)
        self.assertEqual(scheduler.schedule(), [])
        self.assertEqual(scheduler.tasks["too-large"].state, PENDING)
        self.assertEqual(scheduler.advance_time(3), ["too-large"])
        self.assertEqual(scheduler.tasks["too-large"].state, TIMED_OUT)

    def test_negative_transitions_fail_closed(self) -> None:
        scheduler = DeterministicMeshScheduler()
        scheduler.register_worker("alpha", {"cpu"}, 1)
        with self.assertRaises(DuplicateWorkerError):
            scheduler.register_worker("alpha", {"cpu"}, 1)
        scheduler.submit_task("pending", {"quantum"}, 1)
        with self.assertRaises(InvalidTransitionError):
            scheduler.complete_task("pending")

    def test_acceptance_writes_receipt_ledger_snapshot_and_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_mesh_scheduler_acceptance(root, emit_receipt=True)
            self.assertEqual(result["classification"], "LOCAL_PASS")
            self.assertTrue(result["positive_test_passed"])
            self.assertTrue(result["negative_test_passed"])
            self.assertTrue(result["ledger_readback"])
            self.assertFalse(result["hash_used_as_functional_proof"])
            self.assertTrue(Path(result["receipt_path"]).exists())
            self.assertTrue(Path(result["snapshot_path"]).exists())
            self.assertTrue(Path(result["outbox_manifest"]).exists())
            payload = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
            self.assertFalse(payload["os_threads_created"])
            self.assertFalse(payload["remote_workers_contacted"])
            self.assertFalse(payload["host_resources_reserved"])


if __name__ == "__main__":
    unittest.main()
