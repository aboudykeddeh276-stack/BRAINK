#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))
from hardening import canonical_json_bytes, sha256_bytes

LEDGER = ROOT / "reports" / "kex-wbos" / "action-ledger-v2.jsonl"


def verify(path: Path = LEDGER) -> dict:
    if not path.exists():
        return {"ok": True, "ledgerVersion": 2, "entries": 0, "lastReceiptHash": None, "head": "GENESIS"}
    last_hash = "GENESIS"
    entries = 0
    for expected_row, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        entries += 1
        item = json.loads(raw)
        if item.get("ledgerVersion") != 2:
            return {"ok": False, "row": expected_row, "error": "ledgerVersion_mismatch", "observed": item.get("ledgerVersion")}
        if item.get("proofLedgerRow") != expected_row:
            return {"ok": False, "row": expected_row, "error": "proofLedgerRow_mismatch", "observed": item.get("proofLedgerRow")}
        if item.get("parentReceiptHash") != last_hash:
            return {"ok": False, "row": expected_row, "error": "parentReceiptHash_mismatch", "observed": item.get("parentReceiptHash"), "expected": last_hash}
        observed_hash = item.get("receiptHash")
        unsigned = dict(item)
        unsigned.pop("receiptHash", None)
        expected_hash = sha256_bytes(canonical_json_bytes(unsigned))
        if observed_hash != expected_hash:
            return {"ok": False, "row": expected_row, "error": "receiptHash_mismatch", "observed": observed_hash, "expected": expected_hash}
        last_hash = observed_hash
    return {"ok": True, "ledgerVersion": 2, "entries": entries, "lastReceiptHash": last_hash if entries else None, "head": last_hash}


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
