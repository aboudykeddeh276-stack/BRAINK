from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_task_milestone_monitor as monitor


def copy_config(tmp: Path) -> None:
    (tmp / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "task_milestone_registry.json", tmp / "config" / "task_milestone_registry.json")


def write_valid_evidence(tmp: Path, task: monitor.TaskSpec, index: int) -> dict:
    src = tmp / "src" / f"task_{index}.py"
    cmd = tmp / "scripts" / f"task_{index}.command"
    receipt = tmp / "evidence" / f"task_{index}.json"
    ledger = tmp / "runtime_volume" / "proof_bundles.ledger"
    outbox = tmp / "runtime_volume" / "outbox" / f"task_{index}.handoff.json"
    for path in [src, cmd, receipt, ledger, outbox]:
        path.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("print('ok')\n", encoding="utf-8")
    cmd.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    entry_hash = f"entry-{index}"
    receipt.write_text(json.dumps({"task_id": task.task_id, "state": "LOCAL_PASS"}), encoding="utf-8")
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"entry_hash": entry_hash, "task_id": task.task_id}) + "\n")
    outbox.write_text(json.dumps({"task_id": task.task_id, "status": "HANDOFF"}), encoding="utf-8")

    record = {
        "task_id": task.task_id,
        "state": "LOCAL_PASS",
        "receipt_path": str(receipt.relative_to(tmp)),
        "completed_by": "acceptance_harness_agent",
        "completed_at": float(index),
        "source_path": str(src.relative_to(tmp)),
        "command_path": str(cmd.relative_to(tmp)),
        "positive_tests": 1,
        "negative_tests": 1,
        "ledger_path": str(ledger.relative_to(tmp)),
        "ledger_entry_hash": entry_hash,
        "outbox_path": str(outbox.relative_to(tmp)),
        "hash_used_as_functional_proof": False,
        "telemetry_only": False,
    }
    if task.deployment_state == "TARGET_HOST_GATED":
        host = tmp / "evidence" / f"target_host_{index}.json"
        host.write_text(json.dumps({"state": "LOCAL_PASS", "source": "target_host"}), encoding="utf-8")
        record["target_host_evidence_path"] = str(host.relative_to(tmp))
    if task.deployment_state == "PROVIDER_GATED":
        provider = tmp / "evidence" / f"provider_{index}.json"
        provider.write_text(json.dumps({"state": "LOCAL_PASS", "source": "provider"}), encoding="utf-8")
        record["provider_evidence_path"] = str(provider.relative_to(tmp))
    return record


class TaskMilestoneMonitorTests(unittest.TestCase):
    def test_task_registry_expands_to_exactly_100_tasks_and_twenty_checkpoints(self) -> None:
        cfg = monitor.load_config(ROOT)
        tasks = monitor.expand_tasks(cfg)
        self.assertEqual(len(tasks), 100)
        self.assertEqual(len({task.task_id for task in tasks}), 100)
        self.assertEqual(cfg["milestone_interval"], 5)
        self.assertEqual(cfg["milestones"], list(range(5, 101, 5)))

    def test_monitor_without_completion_records_does_not_claim_milestone(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            result = monitor.run_monitor(tmp, emit_receipt=True)
            receipt = result["receipt"]
            self.assertEqual(receipt["valid_completed_tasks"], 0)
            self.assertEqual(receipt["newly_reached_milestones"], [])
            self.assertFalse(receipt["notify_required"])
            self.assertTrue(receipt["ledger_readback"])

    def test_four_valid_tasks_do_not_trigger_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            tasks = monitor.expand_tasks(cfg)
            monitor.write_json(tmp / cfg["completion_source"], [write_valid_evidence(tmp, t, i + 1) for i, t in enumerate(tasks[:4])])
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 4)
            self.assertEqual(result["receipt"]["newly_reached_milestones"], [])

    def test_five_valid_tasks_trigger_checkpoint_once(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            tasks = monitor.expand_tasks(cfg)
            monitor.write_json(tmp / cfg["completion_source"], [write_valid_evidence(tmp, t, i + 1) for i, t in enumerate(tasks[:5])])
            first = monitor.run_monitor(tmp, emit_receipt=True)
            second = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(first["receipt"]["newly_reached_milestones"], [5])
            self.assertTrue(first["receipt"]["notify_required"])
            self.assertEqual(second["receipt"]["newly_reached_milestones"], [])
            self.assertFalse(second["receipt"]["notify_required"])

    def test_jump_from_four_to_twelve_emits_five_and_ten(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            tasks = monitor.expand_tasks(cfg)
            first_records = [write_valid_evidence(tmp, t, i + 1) for i, t in enumerate(tasks[:4])]
            monitor.write_json(tmp / cfg["completion_source"], first_records)
            monitor.run_monitor(tmp, emit_receipt=True)
            records = [write_valid_evidence(tmp, t, i + 1) for i, t in enumerate(tasks[:12])]
            monitor.write_json(tmp / cfg["completion_source"], records)
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 12)
            self.assertEqual(result["receipt"]["newly_reached_milestones"], [5, 10])

    def test_receipt_file_alone_is_not_completion(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            task = monitor.expand_tasks(cfg)[0]
            receipt = tmp / "receipt.json"
            receipt.write_text(json.dumps({"task_id": task.task_id, "state": "LOCAL_PASS"}), encoding="utf-8")
            monitor.write_json(tmp / cfg["completion_source"], [{
                "task_id": task.task_id,
                "state": "LOCAL_PASS",
                "receipt_path": "receipt.json",
                "completed_by": "test_worker",
            }])
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 0)
            reasons = [x["reason"] for x in result["receipt"]["case_study"]["invalid_completion_records"]]
            self.assertIn("executable_source_missing", reasons)

    def test_missing_negative_test_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            task = monitor.expand_tasks(cfg)[0]
            record = write_valid_evidence(tmp, task, 1)
            record["negative_tests"] = 0
            monitor.write_json(tmp / cfg["completion_source"], [record])
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 0)
            self.assertEqual(result["receipt"]["case_study"]["invalid_completion_records"][0]["reason"], "negative_tests_missing")

    def test_hash_and_telemetry_only_records_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            tasks = monitor.expand_tasks(cfg)
            a = write_valid_evidence(tmp, tasks[0], 1)
            b = write_valid_evidence(tmp, tasks[1], 2)
            a["hash_used_as_functional_proof"] = True
            b["telemetry_only"] = True
            monitor.write_json(tmp / cfg["completion_source"], [a, b])
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 0)
            self.assertEqual(result["receipt"]["invalid_completion_records"], 2)

    def test_target_host_gated_task_requires_target_host_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            task = next(t for t in monitor.expand_tasks(cfg) if t.deployment_state == "TARGET_HOST_GATED")
            record = write_valid_evidence(tmp, task, 1)
            Path(tmp / record["target_host_evidence_path"]).unlink()
            monitor.write_json(tmp / cfg["completion_source"], [record])
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 0)
            self.assertEqual(result["receipt"]["case_study"]["invalid_completion_records"][0]["reason"], "target_host_evidence_missing")

    def test_provider_gated_task_requires_provider_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            task = next(t for t in monitor.expand_tasks(cfg) if t.deployment_state == "PROVIDER_GATED")
            record = write_valid_evidence(tmp, task, 1)
            Path(tmp / record["provider_evidence_path"]).unlink()
            monitor.write_json(tmp / cfg["completion_source"], [record])
            result = monitor.run_monitor(tmp, emit_receipt=True)
            self.assertEqual(result["receipt"]["valid_completed_tasks"], 0)
            self.assertEqual(result["receipt"]["case_study"]["invalid_completion_records"][0]["reason"], "provider_evidence_missing")

    def test_manual_record_task_promotion_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copy_config(tmp)
            cfg = monitor.load_config(tmp)
            with self.assertRaises(RuntimeError):
                monitor.record_completion(tmp, cfg, "anything", "receipt.json", "worker")


if __name__ == "__main__":
    unittest.main()
