#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

try:
    from runtime.accountability_receipt_bridge import append_accountability_receipt, root
    from runtime.illlm_ledger import ILLLMImmutableLedger
    from runtime.runtime_registry import RuntimeRegistry
except ImportError:
    from accountability_receipt_bridge import append_accountability_receipt, root
    from illlm_ledger import ILLLMImmutableLedger
    from runtime_registry import RuntimeRegistry


def receipt(decision="ALLOW"):
    body = {
        "schema": "keddeh.accountability-admission.r33.v1",
        "decision": decision,
        "subject": "runtime://braink/existing",
        "action": "MODIFY",
        "requested_claim": "IMPLEMENTED",
        "reasons": [],
        "unresolved": [],
        "preserved_authority": "braink://authority/runtime",
        "evidence_scope": "runtime://braink",
        "claim_scope": "runtime://braink",
    }
    return {**body, "receipt_root": root(body)}


class AccountabilityBridgeTests(unittest.TestCase):
    def test_valid_receipt_appends_and_reads_back(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.jsonl"
            result = append_accountability_receipt(receipt(), ledger_path=ledger)
            self.assertEqual(result["state"], "BRAINK_ILLLM_READBACK_VERIFIED")
            self.assertFalse(result["runtime_authority_mutated"])
            verify = ILLLMImmutableLedger(ledger).verify()
            self.assertEqual(verify["status"], "PASS")
            self.assertEqual(verify["events"], 1)

    def test_invalid_governance_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            r = receipt()
            r["receipt_root"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "ACCOUNTABILITY_RECEIPT_ROOT_INVALID"):
                append_accountability_receipt(r, ledger_path=Path(td) / "ledger.jsonl")

    def test_existing_runtime_is_read_only_and_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "runtime.sqlite3"
            ledger_path = Path(td) / "ledger.jsonl"
            registry = RuntimeRegistry(registry_path)
            before = registry.upsert({
                "runtime_id": "runtime://braink/existing",
                "runtime_class": "PROCESS",
                "command_route": "python3",
                "argv": ["resident-working.py", "--preserve-me"],
                "generation": 7,
                "desired_state": "RUNNING",
                "observed_state": "RUNNING",
                "last_readback": {"status": "PASS", "source": "resident"},
                "author_id": "AKD",
                "authorship_root": "enterprise/governance/AKD_AUTHORSHIP_ROOT.json",
            })
            result = append_accountability_receipt(
                receipt(), ledger_path=ledger_path, registry_path=registry_path,
                runtime_id="runtime://braink/existing"
            )
            after = registry.get("runtime://braink/existing")
            self.assertEqual(before, after)
            self.assertEqual(result["runtime_before"], result["runtime_after"])
            self.assertEqual(result["runtime_before"]["command_route"], "python3")
            self.assertFalse(result["runtime_authority_mutated"])

    def test_unknown_runtime_stays_unresolved_and_is_not_created(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "runtime.sqlite3"
            ledger_path = Path(td) / "ledger.jsonl"
            registry = RuntimeRegistry(registry_path)
            result = append_accountability_receipt(
                receipt(), ledger_path=ledger_path, registry_path=registry_path,
                runtime_id="runtime://braink/not-observed"
            )
            self.assertEqual(result["runtime_before"]["state"], "UNRESOLVED")
            self.assertIsNone(registry.get("runtime://braink/not-observed"))
            self.assertFalse(result["runtime_authority_mutated"])


if __name__ == "__main__":
    unittest.main()
