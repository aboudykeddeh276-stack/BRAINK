#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "modules" / "kex_wbos"))

from modules.kex_wbos.canonical_action_runtime import execute_canonical_action


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    # Use the resident executor's ARMED path: this exercises the real dispatch
    # boundary without requiring or pretending an external actuator exists.
    request = {
        "requestId": "KEX-WBOS-CANONICAL-TEST-1",
        "authority": "A.KEDDEH",
        "actionType": "CANONICAL_BOUNDARY_SELF_TEST",
        "target": "runtime://kex-wbos",
        "payload": {
            "state": 1,
            "nested": {"axis": [-3, -2, 1, 2, 3], "resonance": 0.297},
        },
    }
    result = execute_canonical_action(request)

    require(result["status"] == "ARMED", "resident WBOS executor contract changed")
    proof = result.get("canonicalState", {})
    require(proof.get("schema") == "kex.wbos-canonical-action-receipt.v1", "canonical receipt missing")
    require(proof.get("evidenceLevel") == "SOFTWARE_OBSERVED", "evidence was over-promoted")
    require(proof.get("identityPreserved") is True, "canonical WBOS boundary lost state")
    require(proof.get("ledgerRow", 0) > 0, "canonical action ledger was not written")
    require(proof.get("metrics", {}).get("crossings") == 3, "unexpected canonical crossing count")
    require(proof.get("metrics", {}).get("totalPropagationCost", 0) > 0, "propagation instrumentation missing")

    receipt = {
        "schema": "kex.canonical-wbos-test.v1",
        "state": "PASS",
        "executorState": result["status"],
        "canonicalState": proof,
        "claimBoundary": (
            "This execution proves canonical request/result handling around the resident "
            "WBOS action executor. ARMED is intentionally not reported as an external mutation."
        ),
    }
    out = ROOT / "reports" / "kex-wbos" / "canonical-wbos-test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
