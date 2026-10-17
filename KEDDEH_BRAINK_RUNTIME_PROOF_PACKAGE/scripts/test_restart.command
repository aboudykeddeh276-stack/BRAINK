#!/bin/bash
# Drive a full crash / restart / recovery sequence and print the restart receipt.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACKAGE_ROOT"

PYTHON="${PYTHON:-python3}"

echo "== BrAInK runtime :: restart and recovery =="

PYTHONPATH="$PACKAGE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" - <<'PY'
import json
import os
import shutil
import tempfile

from braink_runtime.ledger import Ledger
from braink_runtime.restart import RestartManager
from braink_runtime.runtime import BrAInKRuntime

workspace = tempfile.mkdtemp(prefix="braink-restart-")
ledger_path = os.path.join(workspace, "ledger.sqlite")
state_path = os.path.join(workspace, "restart_state.json")
config = {
    "ledger_path": ledger_path,
    "state_path": state_path,
    "session_id": "restart-command-session",
}
try:
    print("-- session 1 --")
    runtime = BrAInKRuntime(config)
    print("start        :", runtime.start()["entry_id"])
    print("command      :", runtime.process_command("run diagnostics")["intent"])
    manager = RestartManager(state_path, ledger_path, session_id=config["session_id"])
    state = manager.save_state(runtime.ledger, clean=True)
    print("saved head   :", state.last_entry_id, state.last_entry_hash[:16])
    crash = manager.simulate_unclean_shutdown(runtime.ledger)
    print("crash event  :", crash["event_type"], "entry", crash["entry_id"])
    runtime.ledger.close()

    print("\n-- session 2 (after restart) --")
    reopened = Ledger(ledger_path)
    report = manager.recover(reopened)
    print(json.dumps(report, indent=2, sort_keys=True))
    receipt = manager.generate_restart_receipt(reopened, manager.load_state())
    resumed = reopened.append("RESUMED", {"session_id": config["session_id"]})
    print("\nresumed entry:", resumed.entry_id, resumed.entry_hash[:16])
    print("chain valid  :", reopened.verify_chain())
    reopened.close()

    assert report["chain_valid"] is True
    assert report["tampered_entries"] == []
    assert receipt["continuity_proven"] is True
    print("\nrestart status: RESTART_TESTED")
finally:
    shutil.rmtree(workspace, ignore_errors=True)
PY
