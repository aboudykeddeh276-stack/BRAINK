#!/usr/bin/env python3
"""Canonical-state gate for the resident KEX/WBOS action runtime.

This is the first production integration of the KEX ONE-state invariant.
Requests are canonicalized before the existing executor sees them; executor
results are canonicalized before they leave the WBOS wrapper.  The underlying
executor remains authoritative for mutation semantics and external-action
claim boundaries.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # package import
    from .action_runtime import execute_action
except ImportError:  # direct module execution used by existing WBOS tooling
    from action_runtime import execute_action

from modules.kex_core.canonical_state import CanonicalBoundary, digest, mapping_adapter

BASE = Path(__file__).resolve().parents[2]
CANONICAL_ACTION_LEDGER = BASE / "reports" / "kex-wbos" / "canonical-action-ledger.jsonl"


def _append_transition_receipt(receipt: dict[str, Any]) -> int:
    CANONICAL_ACTION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with CANONICAL_ACTION_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    with CANONICAL_ACTION_LEDGER.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def execute_canonical_action(request: dict[str, Any]) -> dict[str, Any]:
    """Execute one WBOS request with canonical ingress/egress enforcement."""
    if not isinstance(request, dict):
        raise TypeError("canonical WBOS action request must be a mapping")

    authority = str(request.get("authority", ""))
    identity = str(request.get("requestId") or f"REQ-{digest(request)[:16]}")

    boundary = CanonicalBoundary()
    boundary.register(mapping_adapter("wbos-request"))
    boundary.register(mapping_adapter("wbos-result"))

    request_state = boundary.enter(
        "wbos-request",
        request,
        identity=identity,
        authority=authority,
        lineage=("runtime://kex-wbos",),
        dependency_hops=1,
        fan_out=1,
    )

    # The executor receives only the canonical payload, never the caller's
    # mutable object. This is the operational wrapper-boundary invariant.
    canonical_request = dict(request_state.payload)
    raw_result = execute_action(canonical_request)

    result_identity = str(raw_result.get("receiptId") or raw_result.get("actionId") or identity)
    result_state = boundary.enter(
        "wbos-result",
        raw_result,
        identity=result_identity,
        authority=authority,
        lineage=(*request_state.lineage, f"canonical://{request_state.state_digest}"),
        dependency_hops=1,
        fan_out=1,
    )
    outward_result = boundary.exit(
        "wbos-result",
        result_state,
        dependency_hops=1,
        fan_out=1,
    )

    transition = {
        "schema": "kex.wbos-canonical-action-receipt.v1",
        "evidenceLevel": "SOFTWARE_OBSERVED",
        "requestIdentity": request_state.identity,
        "requestCanonicalDigest": request_state.state_digest,
        "resultIdentity": result_state.identity,
        "resultCanonicalDigest": result_state.state_digest,
        "executorStatus": outward_result.get("status"),
        "executorReceiptId": outward_result.get("receiptId"),
        "authority": authority,
        "lineage": list(result_state.lineage),
        "metrics": boundary.metrics(),
        "crossings": [item.as_dict() for item in boundary.evidence],
        "claimBoundary": (
            "Observed proof covers software canonicalization around the resident WBOS "
            "executor and round-trip semantic preservation at this wrapper only."
        ),
    }
    ledger_row = _append_transition_receipt(transition)

    # Preserve the resident action receipt as the outward API while attaching
    # canonical proof metadata. Existing consumers therefore do not lose their
    # action-runtime contract.
    enriched = dict(outward_result)
    enriched["canonicalState"] = {
        "schema": transition["schema"],
        "evidenceLevel": transition["evidenceLevel"],
        "requestDigest": request_state.state_digest,
        "resultDigest": result_state.state_digest,
        "identityPreserved": all(
            ev.identity_preserved is not False for ev in boundary.evidence
        ),
        "ledgerRow": ledger_row,
        "metrics": transition["metrics"],
    }
    return enriched
