from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_workflow_schema_guard as guard


def test_normalize_slug_generates_machine_safe_slug() -> None:
    assert guard.normalize_slug("Enable 3DS retry on soft declines") == "enable-3ds-retry-on-soft-declines"


def test_valid_default_payload_passes_work_item_validation() -> None:
    config = guard.read_json(ROOT / "config" / "workflow_schema.json")
    errors = guard.validate_work_item(guard.default_payload(), config)
    assert errors == []


def test_mutable_status_in_title_is_rejected() -> None:
    config = guard.read_json(ROOT / "config" / "workflow_schema.json")
    payload = guard.default_payload()
    payload["title"] = "[P1][Blocked] Add workflow schema guard"
    errors = guard.validate_work_item(payload, config)
    assert any(error.field == "title" for error in errors)


def test_branch_pr_commit_and_labels_match_schema() -> None:
    config = guard.read_json(ROOT / "config" / "workflow_schema.json")
    assert guard.validate_branch("feature/KEX-98/workflow-schema-guard-service-spine", config)
    assert not guard.validate_branch("feature/no-ref/bad slug", config)
    assert guard.validate_pr_title("KEX-98 Add workflow schema guard to service spine", config)
    assert guard.validate_commit_message("feat(workflow): KEX-98 add schema guard receipts", config)
    assert guard.validate_labels(["wf-lvl-task", "wf-st-in-review", "wf-pr-p1"], config)


def test_workflow_schema_guard_emits_receipt_ledger_and_outbox() -> None:
    final = guard.run_guard(ROOT, emit_receipt=True)
    receipt = final["receipt"]
    assert receipt["promotion_state"] == "LOCAL_PASS"
    assert final["ledger_readback"] is True
    assert final["hash_used_as_functional_proof"] is False
    assert final["schema_enforcement_is_delivery_proof"] is False
    assert Path(receipt["receipt_path"]).exists()
    assert Path(receipt["outbox_manifest"]).exists()
    loaded = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
    assert loaded["receipt"]["schema_id"] == "workflow_schema_v1"
