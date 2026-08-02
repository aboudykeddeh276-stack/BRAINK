from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_task_milestone_monitor as monitor


def copy_config(tmp: Path) -> None:
    (tmp / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "task_milestone_registry.json", tmp / "config" / "task_milestone_registry.json")


def test_task_registry_expands_to_exactly_100_tasks() -> None:
    cfg = monitor.load_config(ROOT)
    tasks = monitor.expand_tasks(cfg)
    assert len(tasks) == 100
    assert len({task.task_id for task in tasks}) == 100


def test_monitor_without_completion_records_does_not_claim_milestone() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        copy_config(tmp)
        result = monitor.run_monitor(tmp, emit_receipt=True)
        receipt = result["receipt"]
        assert receipt["valid_completed_tasks"] == 0
        assert receipt["newly_reached_milestones"] == []
        assert receipt["notify_required"] is False
        assert receipt["ledger_readback"] is True
        assert result["hash_used_as_functional_proof"] is False


def test_monitor_reaches_50_only_with_existing_receipts() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        copy_config(tmp)
        cfg = monitor.load_config(tmp)
        tasks = monitor.expand_tasks(cfg)
        receipt_dir = tmp / "receipts"
        receipt_dir.mkdir()
        records = []
        for task in tasks[:50]:
            receipt = receipt_dir / f"{task.task_id}.json"
            receipt.write_text(json.dumps({"task_id": task.task_id, "status": "LOCAL_PASS"}), encoding="utf-8")
            records.append({
                "task_id": task.task_id,
                "state": "LOCAL_PASS",
                "receipt_path": str(receipt.relative_to(tmp)),
                "completed_by": "test_worker",
                "completed_at": 1.0,
                "hash_used_as_functional_proof": False,
                "telemetry_only": False,
            })
        monitor.write_json(tmp / cfg["completion_source"], records)
        result = monitor.run_monitor(tmp, emit_receipt=True)
        receipt = result["receipt"]
        assert receipt["valid_completed_tasks"] == 50
        assert receipt["newly_reached_milestones"] == [50]
        assert receipt["notify_required"] is True
        assert Path(receipt["outbox_manifest"]).exists()


def test_monitor_does_not_renotify_same_milestone() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        copy_config(tmp)
        cfg = monitor.load_config(tmp)
        tasks = monitor.expand_tasks(cfg)
        receipt_dir = tmp / "receipts"
        receipt_dir.mkdir()
        records = []
        for task in tasks[:50]:
            receipt = receipt_dir / f"{task.task_id}.json"
            receipt.write_text("{}\n", encoding="utf-8")
            records.append({"task_id": task.task_id, "state": "LOCAL_PASS", "receipt_path": str(receipt.relative_to(tmp)), "completed_by": "test_worker"})
        monitor.write_json(tmp / cfg["completion_source"], records)
        first = monitor.run_monitor(tmp, emit_receipt=True)
        second = monitor.run_monitor(tmp, emit_receipt=True)
        assert first["receipt"]["newly_reached_milestones"] == [50]
        assert second["receipt"]["newly_reached_milestones"] == []


def test_hash_and_telemetry_only_records_are_rejected() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        copy_config(tmp)
        cfg = monitor.load_config(tmp)
        task = monitor.expand_tasks(cfg)[0]
        receipt = tmp / "receipt.json"
        receipt.write_text("{}\n", encoding="utf-8")
        monitor.write_json(tmp / cfg["completion_source"], [
            {"task_id": task.task_id, "state": "LOCAL_PASS", "receipt_path": "receipt.json", "completed_by": "test", "hash_used_as_functional_proof": True},
            {"task_id": task.task_id, "state": "LOCAL_PASS", "receipt_path": "receipt.json", "completed_by": "test", "telemetry_only": True},
        ])
        result = monitor.run_monitor(tmp, emit_receipt=True)
        assert result["receipt"]["valid_completed_tasks"] == 0
        assert result["receipt"]["invalid_completion_records"] == 2
