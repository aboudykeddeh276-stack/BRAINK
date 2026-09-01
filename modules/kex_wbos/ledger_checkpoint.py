#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes


def checkpoint_ledger(ledger: Path, checkpoint_dir: Path) -> dict[str, Any]:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    if not ledger.exists():
        head = "GENESIS"
        rows = 0
        ledger_sha = None
    else:
        lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = len(lines)
        if lines:
            last = json.loads(lines[-1])
            head = str(last.get("receiptHash") or "UNVERIFIED_HEAD")
        else:
            head = "GENESIS"
        ledger_sha = sha256_bytes(ledger.read_bytes())

    payload = {
        "checkpointVersion": 1,
        "ledger": ledger.as_posix(),
        "rows": rows,
        "headReceiptHash": head,
        "ledgerSha256": ledger_sha,
        "createdAt": time.time(),
        "boundary": "A retained checkpoint can expose later tail truncation or divergent continuation only when the checkpoint itself survives independently of the damaged ledger.",
    }
    payload["checkpointHash"] = sha256_bytes(canonical_json_bytes(payload))
    target = checkpoint_dir / f"action-ledger-v2-head-{rows:08d}.json"
    atomic_write_text(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {**payload, "path": target.as_posix()}


def verify_checkpoint(ledger: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    checkpoint_rows = int(checkpoint.get("rows", -1))
    checkpoint_head = str(checkpoint.get("headReceiptHash", ""))
    if checkpoint_rows < 0 or not checkpoint_head:
        return {"ok": False, "error": "checkpoint_format_invalid"}

    if not ledger.exists():
        return {
            "ok": checkpoint_rows == 0 and checkpoint_head == "GENESIS",
            "checkpointRows": checkpoint_rows,
            "currentRows": 0,
            "checkpointHead": checkpoint_head,
            "observedCheckpointRowHash": None,
        }

    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    current_rows = len(lines)
    if current_rows < checkpoint_rows:
        return {
            "ok": False,
            "error": "ledger_shorter_than_checkpoint",
            "checkpointRows": checkpoint_rows,
            "currentRows": current_rows,
            "checkpointHead": checkpoint_head,
            "observedCheckpointRowHash": None,
        }

    if checkpoint_rows == 0:
        observed = "GENESIS"
    else:
        try:
            historical_row = json.loads(lines[checkpoint_rows - 1])
            observed = str(historical_row.get("receiptHash") or "")
        except Exception:
            return {
                "ok": False,
                "error": "checkpoint_row_unreadable",
                "checkpointRows": checkpoint_rows,
                "currentRows": current_rows,
            }

    ok = observed == checkpoint_head
    return {
        "ok": ok,
        "error": None if ok else "checkpoint_ancestry_mismatch",
        "checkpointRows": checkpoint_rows,
        "currentRows": current_rows,
        "checkpointHead": checkpoint_head,
        "observedCheckpointRowHash": observed,
        "currentHead": "GENESIS" if not lines else str(json.loads(lines[-1]).get("receiptHash") or ""),
    }
