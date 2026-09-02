#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from action_extensions import append_workbook_rows
from action_runtime import ACTION_LEDGER, dispatch_casepath, execute_action, ingest_source, readback_runtime
from capabilities import mint_capability
from hardening import atomic_write_text, constant_time_bearer_matches, contained_path, require_secure_bind
from idempotency import IdempotencyRegistry
from network_policy import readback_url_allowed
from object_store import ContentAddressedStore
from workbook_semantics import write_semantic_index

sys.path.insert(0, str(ROOT / "scripts" / "kex-ci"))
from verify_action_ledger import verify


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ACTION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ACTION_LEDGER.unlink(missing_ok=True)
    ACTION_LEDGER.with_suffix(ACTION_LEDGER.suffix + ".lock").unlink(missing_ok=True)

    require_secure_bind("127.0.0.1", None)
    try:
        require_secure_bind("10.8.0.2", None)
        raise AssertionError("non-loopback tokenless bind was accepted")
    except RuntimeError:
        pass
    assert constant_time_bearer_matches("Bearer correct", "correct")
    assert not constant_time_bearer_matches("Bearer wrong", "correct")
    assert not constant_time_bearer_matches("Basic correct", "correct")

    cap_secret = "test-only-capability-secret"
    os.environ["KEX_REQUIRE_SCOPED_CAPABILITIES"] = "true"
    os.environ["KEX_CAPABILITY_SECRET"] = cap_secret
    source_cap = mint_capability(cap_secret, actions=["SOURCE_INGEST"], target_prefixes=["KEX_"], ttl_seconds=300, delegated_by="test-suite")
    denied_action = execute_action({
        "authority": "A.KEDDEH",
        "actionType": "CASEPATH_DISPATCH",
        "target": "casepath.com.au",
        "capability": source_cap,
        "payload": {"packetId": "CAP-DENY", "actionQueue": []},
    })
    assert denied_action["status"] == "BLOCKED", denied_action
    assert denied_action["details"]["error"] == "capability_denied", denied_action
    denied_target = execute_action({
        "authority": "A.KEDDEH",
        "actionType": "SOURCE_INGEST",
        "target": "CASEPATH_ACTION_QUEUE",
        "capability": source_cap,
        "payload": {"sourceText": "denied", "sourceFormat": "text"},
    })
    assert denied_target["status"] == "BLOCKED", denied_target
    allowed_capability_ingest = execute_action({
        "authority": "A.KEDDEH",
        "actionType": "SOURCE_INGEST",
        "target": "KEX_RUNTIME_MODEL",
        "capability": source_cap,
        "payload": {"sourceText": "capability-authorized", "sourceFormat": "text"},
    })
    assert allowed_capability_ingest["status"] == "MUTATED", allowed_capability_ingest
    os.environ.pop("KEX_REQUIRE_SCOPED_CAPABILITIES", None)
    os.environ.pop("KEX_CAPABILITY_SECRET", None)

    # Registry primitive and dispatcher integration both get tested.
    idem_path = ROOT / "runtime" / "hardening-tests" / "idempotency.json"
    idem_path.parent.mkdir(parents=True, exist_ok=True)
    idem_path.unlink(missing_ok=True)
    idem_path.with_suffix(idem_path.suffix + ".lock").unlink(missing_ok=True)
    idem = IdempotencyRegistry(idem_path)
    command = {"authority": "A.KEDDEH", "actionType": "SOURCE_INGEST", "target": "KEX_RUNTIME_MODEL", "payload": {"sourceText": "once"}}
    begin = idem.begin("CMD-001", command)
    assert begin["state"] == "NEW", begin
    assert idem.begin("CMD-001", command)["state"] == "INFLIGHT"
    synthetic_receipt = {"receiptHash": "abc123", "status": "MUTATED", "mutated": True}
    idem.complete("CMD-001", begin["requestHash"], synthetic_receipt)
    assert idem.begin("CMD-001", command)["receipt"] == synthetic_receipt
    assert idem.begin("CMD-001", {**command, "target": "DIFFERENT"})["state"] == "CONFLICT"

    dispatch_key = f"E2E-{uuid.uuid4().hex}"
    idempotent_request = {
        "authority": "A.KEDDEH",
        "actionType": "SOURCE_INGEST",
        "target": "KEX_RUNTIME_MODEL",
        "idempotencyKey": dispatch_key,
        "payload": {"sourceText": "execute-once-through-dispatcher", "sourceFormat": "text"},
    }
    first_receipt = execute_action(idempotent_request)
    second_receipt = execute_action(idempotent_request)
    assert first_receipt["status"] == "MUTATED", first_receipt
    assert second_receipt == first_receipt, (first_receipt, second_receipt)
    conflict_receipt = execute_action({**idempotent_request, "target": "OTHER_TARGET"})
    assert conflict_receipt["status"] == "BLOCKED", conflict_receipt
    assert conflict_receipt["details"]["error"] == "idempotency_key_conflict", conflict_receipt

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

    outside = readback_runtime({"target": "/etc/passwd"})
    assert outside["status"] == "FAIL" and outside["observedState"] == "PATH_OUTSIDE_RUNTIME_ROOT", outside
    metadata_allowed, metadata_policy = readback_url_allowed("http://169.254.169.254/latest/meta-data")
    assert metadata_allowed is False, metadata_policy
    metadata_readback = readback_runtime({"target": "http://169.254.169.254/latest/meta-data"})
    assert metadata_readback["status"] == "FAIL" and metadata_readback["observedState"] == "READBACK_DESTINATION_BLOCKED", metadata_readback
    loopback_allowed, _ = readback_url_allowed("http://127.0.0.1:8790/api/health")
    assert loopback_allowed is True

    bad_dispatch = dispatch_casepath({
        "authority": "A.KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH",
        "packetId": "../../escape",
        "activeTarget": "casepath.com.au",
        "processId": "CASEPATH-PROC-001",
        "actionQueue": [],
    })
    assert bad_dispatch["status"] == "FAIL" and bad_dispatch["mutated"] is False, bad_dispatch
    assert bad_dispatch["details"]["error"] == "invalid_packet_id", bad_dispatch
    assert bad_dispatch["receiptHash"], bad_dispatch

    payload = "KEX hardening content-address test"
    ingest = ingest_source({"authority": "A.KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH", "sourceText": payload, "sourceFormat": "text", "target": "KEX_RUNTIME_MODEL"})
    assert ingest["status"] == "MUTATED", ingest
    object_id = ingest["details"]["objectId"]
    expected_digest = hashlib.sha256(payload.encode()).hexdigest()
    assert object_id == f"sha256:{expected_digest}", ingest
    assert ContentAddressedStore(ROOT / "runtime" / "objects").get(object_id) == payload.encode()

    workbook_id = f"HARDENING_{uuid.uuid4().hex[:8]}"
    workbook_path = ROOT / "runtime" / "workbooks" / f"{workbook_id}.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "LEDGER"
    ws.append(["id", "value", "derived"])
    ws.append([1, 10, "=B2*2"])
    ws.append([2, 20, "=B3*2"])
    cycle = wb.create_sheet("CYCLE")
    cycle["A1"] = "=B1"
    cycle["B1"] = "=A1"
    wb.save(workbook_path)

    semantics = write_semantic_index(workbook_path)
    assert semantics["formulaCellCount"] == 4, semantics
    assert semantics["dependencyEdgeCount"] >= 4, semantics
    assert semantics["cycleCount"] >= 1, semantics
    semantic_payload = json.loads(Path(semantics["sidecar"]).read_text())
    assert semantic_payload["graphHash"] == semantics["graphHash"], semantics
    assert any(len(component) >= 2 for component in semantic_payload["cycles"]), semantic_payload["cycles"]

    before = sha(workbook_path)
    invalid = append_workbook_rows(workbook_id, "LEDGER", {"rows": [{"id": 3, "value": 30, "derived": "=B4*2"}, "not-an-object"]})
    after = sha(workbook_path)
    assert invalid["status"] == "FAIL" and invalid["mutated"] is False and before == after, invalid
    valid = append_workbook_rows(workbook_id, "LEDGER", {"rows": [{"id": 3, "value": 30, "derived": "=B4*2"}]})
    assert valid["status"] == "MUTATED" and valid["mutated"] is True, valid
    assert valid["beforeHash"] != valid["afterHash"], valid

    replay = verify(ACTION_LEDGER)
    assert replay["ok"] is True and replay["ledgerVersion"] == 2, replay
    assert replay["entries"] >= 9 and replay["head"] != "GENESIS", replay

    workbook_path.unlink(missing_ok=True)
    Path(semantics["sidecar"]).unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    idem_path.unlink(missing_ok=True)
    idem_path.with_suffix(idem_path.suffix + ".lock").unlink(missing_ok=True)
    print(json.dumps({
        "status": "RUNTIME_HARDENING_PASS",
        "receiptReplay": replay,
        "contentAddress": object_id,
        "workbookGraphHash": semantics["graphHash"],
        "workbookCycleCount": semantics["cycleCount"],
        "idempotencyReceipt": first_receipt["receiptId"],
        "capabilityBoundary": "cross-action and cross-target denial covered by test oracle",
        "idempotencyBoundary": "duplicate suppression and ambiguous-inflight blocking covered; distributed exactly-once is not claimed",
        "networkBoundary": "metadata/link-local readback blocked unless policy changes explicitly",
    }, indent=2))


if __name__ == "__main__":
    main()
