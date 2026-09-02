from pathlib import Path
import json
import tempfile

from enterprise.engineering_control_plane_r24 import AppendOnlyLedger
from enterprise.engineering_ledger_recovery_r24 import recover_incomplete_tail

with tempfile.TemporaryDirectory(prefix="braink-r24-ledger-recovery-") as td:
    path = Path(td) / "engineering-ledger.jsonl"
    ledger = AppendOnlyLedger(path)
    r1 = ledger.append("DISCOVERY_AUDIT", "BRAINK", {"resident": 1})
    r2 = ledger.append("SOURCE_RECONCILIATION", "BRAINK", {"delta_count": 0})
    verified_prefix = path.read_bytes()

    torn = b'{"schema":"braink.r24.ledger-record/v2","event_type":"TORN"'
    with path.open("ab") as fh:
        fh.write(torn)
        fh.flush()

    failed = False
    try:
        AppendOnlyLedger(path)
    except (json.JSONDecodeError, RuntimeError):
        failed = True
    assert failed, "torn tail must not load as a valid ledger"

    recovery = recover_incomplete_tail(path)
    assert recovery["status"] == "RECOVERED_INCOMPLETE_TAIL"
    assert recovery["fragment_bytes"] == len(torn)
    assert Path(recovery["quarantine_path"]).read_bytes() == torn
    assert path.read_bytes() == verified_prefix
    assert recovery["recovered_root"] == r2["record_root"]

    restored = AppendOnlyLedger(path)
    assert restored.ledger_root == r2["record_root"]
    r3 = restored.append("RECOVERY_RECEIPT", "BRAINK", {
        "classification": "TORN_TAIL_QUARANTINED",
        "fragment_sha256": recovery["fragment_sha256"],
    })
    assert r3["predecessor_root"] == r2["record_root"]

    complete_corrupt = Path(td) / "complete-corrupt.jsonl"
    complete_corrupt.write_text('{"invalid":true}\n', encoding="utf-8")
    refused = False
    try:
        recover_incomplete_tail(complete_corrupt)
    except RuntimeError as exc:
        refused = str(exc) == "LEDGER_TAIL_IS_COMPLETE_REFUSE_RECOVERY"
    assert refused, "complete-line corruption must never be silently truncated"

print("R24_ENGINEERING_LEDGER_RECOVERY_PASS")
