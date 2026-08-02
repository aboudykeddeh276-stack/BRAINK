from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_workflow_schema_guard as guard


class WorkflowSchemaGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = guard.read_json(ROOT / "config" / "workflow_schema.json")

    def test_normalize_slug_generates_machine_safe_slug(self) -> None:
        self.assertEqual(
            guard.normalize_slug("Enable 3DS retry on soft declines"),
            "enable-3ds-retry-on-soft-declines",
        )

    def test_valid_default_payload_passes_work_item_validation(self) -> None:
        errors = guard.validate_work_item(guard.default_payload(), self.config)
        self.assertEqual(errors, [])

    def test_mutable_status_in_title_is_rejected(self) -> None:
        payload = guard.default_payload()
        payload["title"] = "[P1][Blocked] Add workflow schema guard"
        errors = guard.validate_work_item(payload, self.config)
        self.assertTrue(any(error.field == "title" for error in errors))

    def test_branch_pr_commit_and_labels_match_schema(self) -> None:
        self.assertTrue(
            guard.validate_branch(
                "feature/KEX-98/workflow-schema-guard-service-spine",
                self.config,
            )
        )
        self.assertFalse(guard.validate_branch("feature/no-ref/bad slug", self.config))
        self.assertTrue(
            guard.validate_pr_title(
                "KEX-98 Add workflow schema guard to service spine",
                self.config,
            )
        )
        self.assertTrue(
            guard.validate_commit_message(
                "feat(workflow): KEX-98 add schema guard receipts",
                self.config,
            )
        )
        self.assertTrue(
            guard.validate_labels(
                ["wf-lvl-task", "wf-st-in-review", "wf-pr-p1"],
                self.config,
            )
        )

    def test_workflow_schema_guard_emits_receipt_ledger_and_outbox(self) -> None:
        final = guard.run_guard(ROOT, emit_receipt=True)
        receipt = final["receipt"]
        self.assertEqual(receipt["promotion_state"], "LOCAL_PASS")
        self.assertIs(final["ledger_readback"], True)
        self.assertIs(final["hash_used_as_functional_proof"], False)
        self.assertIs(final["schema_enforcement_is_delivery_proof"], False)
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        loaded = json.loads(
            Path(receipt["receipt_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(loaded["receipt"]["schema_id"], "workflow_schema_v1")


if __name__ == "__main__":
    unittest.main()
