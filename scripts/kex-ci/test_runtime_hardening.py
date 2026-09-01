#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import sys
import uuid
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from action_extensions import append_workbook_rows
from action_runtime import dispatch_casepath, readback_runtime
from hardening import atomic_write_text, constant_time_bearer_matches, contained_path, require_secure_bind


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    # Authentication membrane.
    require_secure_bind("127.0.0.1", None)
    try:
        require_secure_bind("10.8.0.2", None)
        raise AssertionError("non-loopback tokenless bind was accepted")
    except RuntimeError:
        pass
    assert constant_time_bearer_matches("Bearer correct", "correct")
    assert not constant_time_bearer_matches("Bearer wrong", "correct")
    assert not constant_time_bearer_matches("Basic correct", "correct")

    # Filesystem containment and atomic write.
    hardening_dir = ROOT / "runtime" / "hardening-tests"
    hardening_dir.mkdir(parents=True, exist_ok=True)
    target = contained_path(ROOT, hardening_dir / "atomic.txt")
    atomic_write_text(target, "state-v1")
    assert target.read_text() == "state-v1"
    try:
        contained_path(ROOT, Path("/tmp/kex-escape"))
        raise AssertionError("path escape accepted")
    except ValueError:
        pass

    # Arbitrary host-file readback must be rejected.
    outside = readback_runtime({"target": "/etc/passwd"})
    assert outside["status"] == "FAIL", outside
    assert outside["observedState"] == "PATH_OUTSIDE_RUNTIME_ROOT", outside

    # Casepath packet IDs cannot become paths.
    bad_dispatch = dispatch_casepath({
        "authority": "A.KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH",
        "packetId": "../../escape",
        "activeTarget": "casepath.com.au",
        "processId": "CASEPATH-PROC-001",
        "actionQueue": [],
    })
    assert bad_dispatch["status"] == "FAIL", bad_dispatch
    assert bad_dispatch["mutated"] is False, bad_dispatch
    assert bad_dispatch["details"]["error"] == "invalid_packet_id", bad_dispatch

    # Workbook mutation must prevalidate the whole request before writing.
    workbook_id = f"HARDENING_{uuid.uuid4().hex[:8]}"
    workbook_path = ROOT / "runtime" / "workbooks" / f"{workbook_id}.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "LEDGER"
    ws.append(["id", "value"])
    ws.append([1, "original"])
    wb.save(workbook_path)
    before = sha(workbook_path)
    invalid = append_workbook_rows(workbook_id, "LEDGER", {"rows": [{"id": 2, "value": "valid"}, "not-an-object"]})
    after = sha(workbook_path)
    assert invalid["status"] == "FAIL", invalid
    assert invalid["mutated"] is False, invalid
    assert before == after, (before, after)

    valid = append_workbook_rows(workbook_id, "LEDGER", {"rows": [{"id": 2, "value": "committed"}]})
    assert valid["status"] == "MUTATED", valid
    assert valid["mutated"] is True, valid
    assert valid["beforeHash"] != valid["afterHash"], valid

    workbook_path.unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    print("RUNTIME_HARDENING_PASS")


if __name__ == "__main__":
    main()
