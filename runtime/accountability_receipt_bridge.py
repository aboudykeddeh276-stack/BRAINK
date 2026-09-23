#!/usr/bin/env python3
"""BRAINK bridge for externally governed R33 accountability decisions.

The governance decision remains governance-owned.  This bridge validates the
receipt, optionally snapshots an existing BRAINK runtime record read-only, then
appends the decision into the resident canonical IL-LLM ledger and reads it back.
It never mutates runtime registry authority or recreates governance policy.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from runtime.illlm_ledger import ILLLMImmutableLedger
    from runtime.runtime_registry import RuntimeRegistry
except ImportError:  # direct execution from runtime/
    from illlm_ledger import ILLLMImmutableLedger
    from runtime_registry import RuntimeRegistry

GOVERNANCE_SCHEMA = "keddeh.accountability-admission.r33.v1"
BRIDGE_SCHEMA = "braink.accountability-ledger-bridge.r33.v1"
VALID_DECISIONS = {"ALLOW", "DENY", "DEFER"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def verify_governance_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("schema") != GOVERNANCE_SCHEMA:
        raise ValueError("ACCOUNTABILITY_RECEIPT_SCHEMA_INVALID")
    if receipt.get("decision") not in VALID_DECISIONS:
        raise ValueError("ACCOUNTABILITY_DECISION_INVALID")
    supplied = str(receipt.get("receipt_root") or "")
    body = {k: v for k, v in receipt.items() if k != "receipt_root"}
    if not supplied or root(body) != supplied:
        raise ValueError("ACCOUNTABILITY_RECEIPT_ROOT_INVALID")
    if not receipt.get("subject") or not receipt.get("action"):
        raise ValueError("ACCOUNTABILITY_RECEIPT_IDENTITY_INVALID")


def snapshot_runtime(registry_path: str | Path | None, runtime_id: str | None) -> dict[str, Any] | None:
    """Read one existing BRAINK runtime record without changing it."""
    if not registry_path or not runtime_id:
        return None
    registry = RuntimeRegistry(registry_path)
    record = registry.get(runtime_id)
    if record is None:
        return {"runtime_id": runtime_id, "state": "UNRESOLVED", "mutated": False}
    return {
        "runtime_id": runtime_id,
        "state": "OBSERVED_EXISTING",
        "state_root": record.get("state_root"),
        "runtime_class": record.get("runtime_class"),
        "command_route": record.get("command_route"),
        "desired_state": record.get("desired_state"),
        "observed_state": record.get("observed_state"),
        "authorship_root": record.get("authorship_root"),
        "mutated": False,
    }


def append_accountability_receipt(
    receipt: Mapping[str, Any],
    *,
    ledger_path: str | Path | None = None,
    registry_path: str | Path | None = None,
    runtime_id: str | None = None,
) -> dict[str, Any]:
    verify_governance_receipt(receipt)
    runtime_before = snapshot_runtime(registry_path, runtime_id)

    correlation_id = f"accountability:{receipt['receipt_root']}"
    ledger = ILLLMImmutableLedger(ledger_path)
    payload = {
        "schema": BRIDGE_SCHEMA,
        "governance_receipt_root": receipt["receipt_root"],
        "decision": receipt["decision"],
        "subject": receipt["subject"],
        "action": receipt["action"],
        "requested_claim": receipt.get("requested_claim"),
        "preserved_authority": receipt.get("preserved_authority"),
        "evidence_scope": receipt.get("evidence_scope"),
        "claim_scope": receipt.get("claim_scope"),
        "runtime_snapshot": runtime_before,
        "authority_mutated": False,
    }
    event = ledger.append(
        source_uri="governance://general-governance/r33/accountability",
        source_level="ESTATE_GOVERNANCE_DECISION",
        semantic_type="ACCOUNTABILITY_ADMISSION_DECISION",
        correlation_id=correlation_id,
        payload=payload,
        lexical_state={
            "subject": receipt["subject"],
            "action": receipt["action"],
            "decision": receipt["decision"],
        },
        illlm_state={
            "governance_receipt_root": receipt["receipt_root"],
            "preserved_authority": receipt.get("preserved_authority"),
            "evidence_scope": receipt.get("evidence_scope"),
            "claim_scope": receipt.get("claim_scope"),
        },
    )

    matches = ledger.read_by_correlation(correlation_id)
    if not matches or matches[-1].get("event_root") != event.event_root:
        raise RuntimeError("ACCOUNTABILITY_LEDGER_READBACK_FAILED")
    if ledger.verify().get("status") != "PASS":
        raise RuntimeError("ACCOUNTABILITY_LEDGER_CHAIN_FAILED")

    runtime_after = snapshot_runtime(registry_path, runtime_id)
    if runtime_before is not None and runtime_after != runtime_before:
        raise RuntimeError("ACCOUNTABILITY_BRIDGE_MUTATED_RUNTIME_AUTHORITY")

    return {
        "schema": BRIDGE_SCHEMA,
        "state": "BRAINK_ILLLM_READBACK_VERIFIED",
        "governance_receipt_root": receipt["receipt_root"],
        "ledger_event_root": event.event_root,
        "correlation_id": correlation_id,
        "runtime_before": runtime_before,
        "runtime_after": runtime_after,
        "runtime_authority_mutated": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--runtime-id")
    args = parser.parse_args()
    result = append_accountability_receipt(
        json.loads(args.receipt.read_text(encoding="utf-8")),
        ledger_path=args.ledger,
        registry_path=args.registry,
        runtime_id=args.runtime_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
