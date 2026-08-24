#!/bin/bash
# Build a fresh ledger, append events, verify the hash chain and prove that
# tampering is detected.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACKAGE_ROOT"

PYTHON="${PYTHON:-python3}"

echo "== BrAInK runtime :: ledger integrity =="

PYTHONPATH="$PACKAGE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" - <<'PY'
import json
import os
import shutil
import sqlite3
import tempfile

from braink_runtime.ledger import Ledger

workspace = tempfile.mkdtemp(prefix="braink-verify-ledger-")
path = os.path.join(workspace, "ledger.sqlite")
try:
    ledger = Ledger(path)
    ledger.append("RUNTIME_START", {"source": "verify_ledger.command"})
    ledger.append("COMMAND", {"intent": "VERIFY", "tokens": ["verify", "ledger"]})
    ledger.append("RUNTIME_SHUTDOWN", {"clean": True})
    receipt = ledger.export_receipt()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    assert receipt["chain_valid"] is True, "clean chain must verify"
    assert receipt["tampered_entries"] == []
    ledger.close()

    # Negative control: corrupt the store directly and prove detection.
    conn = sqlite3.connect(path)
    conn.execute("UPDATE ledger SET payload = ? WHERE entry_id = 1", ('{"source":"TAMPERED"}',))
    conn.commit()
    conn.close()

    reopened = Ledger(path)
    tampered = reopened.detect_tamper()
    print("\nafter deliberate corruption:")
    print("  chain_valid      :", reopened.verify_chain())
    print("  tampered_entries :", tampered)
    reopened.close()
    assert tampered, "tampering must be detected"
    print("\nledger integrity: LOCALLY_PROVEN")
finally:
    shutil.rmtree(workspace, ignore_errors=True)
PY
