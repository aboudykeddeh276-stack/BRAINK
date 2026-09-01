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
        "boundary": "A retained checkpoint can expose later tail truncation only when the checkpoint itself survives independently of the truncated ledger.",
    }
    payload["checkpointHash"] = sha256_bytes(canonical_json_bytes(payload))
    target = checkpoint_dir / f"action-ledger-v2-head-{rows:08d}.json"
    atomic_write_text(target, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {**payload, "path": target.as_posix()}


def verify_checkpoint(ledger: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    current = checkpoint_ledger(ledger, ledger.parent / ".checkpoint-probe")
    try:
        ok = (
            int(current["rows"]) >= int(checkpoint["rows"])
            and (current["rows"] != checkpoint["rows"] or current["headReceiptHash"] == checkpoint["headReceiptHash"])
        )
        return {
            "ok": ok,
            "checkpointRows": checkpoint["rows"],
            "currentRows": current["rows"],
            "checkpointHead": checkpoint["headReceiptHash"],
            "currentHead": current["headReceiptHash"],
        }
    finally:
        probe = Path(current["path"])
        probe.unlink(missing_ok=True)
        try:
            probe.parent.rmdir()
        except OSError:
            pass
