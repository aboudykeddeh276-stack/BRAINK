#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from action_extensions import append_workbook_rows
from action_runtime import ACTION_LEDGER, dispatch_casepath, ingest_source, readback_runtime
from hardening import atomic_write_text, constant_time_bearer_matches, contained_path, require_secure_bind
from object_store import ContentAddressedStore
from workbook_semantics import write_semantic_index

sys.path.insert(0, str(ROOT / "scripts" / "kex-ci"))
from verify_action_ledger import verify


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    # Make this test independent of earlier local runtime receipts.
    ACTION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ACTION_LEDGER.unlink(missing_ok=True)
    ACTION_LEDGER.with_suffix(ACTION_LEDGER.suffix + ".lock").unlink(missing_ok=True)

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
    assert bad_dispatch["proofLedgerRow"] == 1, bad_dispatch
    assert bad_dispatch["receiptHash"], bad_dispatch

    # Content-addressed ingest: path is a carrier, object ID is content identity.
    payload = "KEX hardening content-address test"
    ingest = ingest_source({
        "authority": "A.KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH",
        "sourceText": payload,
        "sourceFormat": "text",
        "target": "KEX_RUNTIME_MODEL",
    })
    assert ingest["status"] == "MUTATED", ingest
    object_id = ingest["details"]["objectId"]
    expected_digest = hashlib.sha256(payload.encode()).hexdigest()
    assert object_id == f"sha256:{expected_digest}", ingest
    store = ContentAddressedStore(ROOT / "runtime" / "objects")
    assert store.get(object_id) == payload.encode()

    # Workbook mutation must prevalidate the whole request before writing.
    workbook_id = f"HARDENING_{uuid.uuid4().hex[:8]}"
    workbook_path = ROOT / "runtime" / "workbooks" / f"{workbook_id}.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "LEDGER"
    ws.append(["id", "value", "derived"])
    ws.append([1, 10, "=B2*2"])
    ws.append([2, 20, "=B3*2"])
    wb.save(workbook_path)

    semantics = write_semantic_index(workbook_path)
    assert semantics["formulaCellCount"] == 2, semantics
    assert semantics["dependencyEdgeCount"] >= 2, semantics
    semantic_payload = json.loads(Path(semantics["sidecar"]).read_text())
    assert semantic_payload["graphHash"] == semantics["graphHash"], semantics

    before = sha(workbook_path)
    invalid = append_workbook_rows(workbook_id, "LEDGER", {"rows": [{"id": 3, "value": 30, "derived": "=B4*2"}, "not-an-object"]})
    after = sha(workbook_path)
    assert invalid["status"] == "FAIL", invalid
    assert invalid["mutated"] is False, invalid
    assert before == after, (before, after)

    valid = append_workbook_rows(workbook_id, "LEDGER", {"rows": [{"id": 3, "value": 30, "derived": "=B4*2"}]})
    assert valid["status"] == "MUTATED", valid
    assert valid["mutated"] is True, valid
    assert valid["beforeHash"] != valid["afterHash"], valid

    # Event-ledger replay must match the exact persisted receipt semantics.
    replay = verify(ACTION_LEDGER)
    assert replay["ok"] is True, replay
    assert replay["entries"] >= 4, replay

    workbook_path.unlink(missing_ok=True)
    Path(semantics["sidecar"]).unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    print(json.dumps({
        "status": "RUNTIME_HARDENING_PASS",
        "receiptReplay": replay,
        "contentAddress": object_id,
        "workbookGraphHash": semantics["graphHash"],
    }, indent=2))


if __name__ == "__main__":
    main()
