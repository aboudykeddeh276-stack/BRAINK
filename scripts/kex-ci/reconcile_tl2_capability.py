#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes
from outbox import DurableOutbox

FABRIC_DIR = ROOT / "reports" / "kex-wbos" / "capability-fabric"
TL2_REPORT = ROOT / "reports" / "kex-wbos" / "tl2-deployment.json"
OUTBOX_PATH = ROOT / "runtime" / "outbox" / "external-actions-v1.json"
RECONCILIATION = ROOT / "reports" / "kex-wbos" / "tl2-capability-reconciliation.json"


def latest_fabric_report() -> Path:
    reports = sorted(FABRIC_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not reports:
        raise RuntimeError("no capability fabric report found")
    return reports[-1]


def main() -> int:
    fabric_path = latest_fabric_report()
    fabric = json.loads(fabric_path.read_text(encoding="utf-8"))
    tl2 = json.loads(TL2_REPORT.read_text(encoding="utf-8"))
    if fabric.get("status") != "LOCAL_CAPABILITY_FABRIC_VERIFIED":
        raise RuntimeError("local capability fabric was not verified")
    if tl2.get("status") != "VERIFIED" or tl2.get("promotion") != "TL2_LIVE":
        raise RuntimeError("TL2 participant receipt is not verified")

    outbox_item = fabric.get("outbox", {}).get("item", {})
    key = str(outbox_item.get("idempotencyKey", ""))
    if not key:
        raise RuntimeError("fabric report has no outbox idempotency key")

    participant_receipt = {
        "participant": "tlvpn://kex/tl2",
        "promotion": tl2.get("promotion"),
        "status": tl2.get("status"),
        "address": tl2.get("address"),
        "receiptHash": tl2.get("receiptHash"),
        "readback": tl2.get("readback"),
        "supervisor": tl2.get("supervisor"),
    }
    delivered = DurableOutbox(OUTBOX_PATH).mark_delivered(key, participant_receipt)

    report = {
        "recordId": "KEX_TL2_CAPABILITY_RECONCILIATION_R1",
        "status": "VERIFIED",
        "fabricRunId": fabric.get("runId"),
        "fabricReportHash": fabric.get("reportHash"),
        "fabricReportPath": fabric_path.relative_to(ROOT).as_posix(),
        "outboxId": delivered.get("outboxId"),
        "outboxState": delivered.get("state"),
        "participantReceiptHash": delivered.get("participantReceiptHash"),
        "tl2Promotion": tl2.get("promotion"),
        "tl2ReceiptHash": tl2.get("receiptHash"),
        "boundary": "This proves the locally staged TL2 intent was reconciled to the observed TL2 participant receipt. It does not imply PUBLIC_LIVE or distributed exactly-once execution.",
    }
    report["reconciliationHash"] = sha256_bytes(canonical_json_bytes(report))
    atomic_write_text(RECONCILIATION, json.dumps(report, indent=2, sort_keys=True) + "\n")
    persisted = json.loads(RECONCILIATION.read_text(encoding="utf-8"))
    if persisted != report:
        raise RuntimeError("reconciliation persistence divergence")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
