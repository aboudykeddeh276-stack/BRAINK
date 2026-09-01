#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "modules" / "kex_wbos"))

from action_runtime import dispatch_casepath  # noqa: E402


def main() -> int:
    packet_id = "CASEPATH_MANAGEMENT_TEST_R1"
    result = dispatch_casepath({
        "authority": "A. KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH",
        "packetId": packet_id,
        "activeTarget": "casepath.com.au",
        "processId": "CASEPATH-PROC-001",
        "actionQueue": [
            {"id": "T1", "action": "classify_public_element"},
            {"id": "T2", "action": "bind_claim_to_service_and_evidence"},
        ],
        "proofTarget": "runtime/casepath-dispatch/CASEPATH_MANAGEMENT_PROOF.jsonl",
    })
    assert result["status"] == "MUTATED", result
    assert result["mutated"] is True, result
    details = result["details"]
    assert details["processId"] == "CASEPATH-PROC-001", result
    assert details["ownerTeam"] == "CASEPATH_SERVICE_SURFACE_TEAM", result
    assert details["proofAfterHash"], result

    packet_path = BASE / details["path"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["processId"] == "CASEPATH-PROC-001"
    assert packet["ownerTeam"] == "CASEPATH_SERVICE_SURFACE_TEAM"
    assert packet["accountability"]["promotionCriterion"]
    assert len(packet["actionQueue"]) == 2
    for action in packet["actionQueue"]:
        assert action["processId"] == "CASEPATH-PROC-001"
        assert action["ownerTeam"] == "CASEPATH_SERVICE_SURFACE_TEAM"
        assert action["runtimeScope"]
        assert action["serviceDeliveryScope"]
        assert action["promotionCriterion"]

    rejected = dispatch_casepath({
        "authority": "A. KEDDEH",
        "packetId": "CASEPATH_MANAGEMENT_INVALID_PROCESS",
        "activeTarget": "casepath.com.au",
        "processId": "CASEPATH-PROC-DOES-NOT-EXIST",
        "actionQueue": [],
    })
    assert rejected["status"] == "FAIL", rejected
    assert rejected["mutated"] is False, rejected
    assert rejected["details"]["error"] == "unknown_casepath_process", rejected

    print(json.dumps({
        "status": "PASS",
        "managedDispatch": result,
        "invalidProcessRejection": rejected,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
