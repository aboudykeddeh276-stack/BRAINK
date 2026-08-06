import os
import shutil
import tempfile

import pytest

from braink_runtime import __version__
from braink_runtime.ledger import Ledger
from braink_runtime.receipts import (
    generate_package_manifest,
    generate_test_results,
    generate_validation_receipt,
)
from braink_runtime.restart import RestartManager
from braink_runtime.runtime import BrAInKRuntime
from braink_runtime.signer import TestSigner


@pytest.fixture()
def workspace():
    path = tempfile.mkdtemp(prefix="braink-e2e-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _config(workspace, session_id="e2e-session"):
    return {
        "ledger_path": os.path.join(workspace, "ledger.sqlite"),
        "state_path": os.path.join(workspace, "restart_state.json"),
        "namespace": "braink",
        "version": __version__,
        "session_id": session_id,
    }


def test_full_lifecycle(workspace):
    runtime = BrAInKRuntime(_config(workspace))
    start = runtime.start()
    assert start["status"] == "STARTED"
    assert start["entry_id"] == 1
    assert start["signature"]["algorithm"] == "HMAC-SHA256"

    execute = runtime.process_command("run diagnostics")
    assert execute["intent"] == "EXECUTE"
    assert execute["accepted"] is True

    verify = runtime.process_command("verify ledger")
    assert verify["intent"] == "VERIFY"
    assert verify["entry_id"] == 3

    status = runtime.get_status()
    assert status["started"] is True
    assert status["commands_processed"] == 2
    assert status["ledger"]["chain_valid"] is True
    assert status["signer"]["production_signer"] == "DEFINED"
    assert status["dns"]["status_cap"] == "LOCALLY_EXECUTED"
    assert status["dns"]["authoritative_external_confirmed"] is False

    shutdown = runtime.shutdown(clean=True)
    assert shutdown["status"] == "SHUTDOWN"
    assert shutdown["chain_valid"] is True
    assert shutdown["last_entry_id"] == 4


def test_unknown_command_is_recorded(workspace):
    runtime = BrAInKRuntime(_config(workspace, "unknown-session"))
    runtime.start()
    result = runtime.process_command("banana banana")
    assert result["intent"] == "UNKNOWN"
    assert result["accepted"] is True
    runtime.shutdown()


def test_malformed_command_is_rejected_but_logged(workspace):
    runtime = BrAInKRuntime(_config(workspace, "bad-session"))
    runtime.start()
    result = runtime.process_command("   ")
    assert result["accepted"] is False
    assert result["intent"] == "INVALID"
    assert result["error"]
    runtime.shutdown()


def test_process_command_before_start_raises(workspace):
    runtime = BrAInKRuntime(_config(workspace, "nostart-session"))
    with pytest.raises(RuntimeError):
        runtime.process_command("run")
    runtime.ledger.close()


def test_runtime_requires_config():
    with pytest.raises(ValueError):
        BrAInKRuntime(None)


def test_restart_preserves_ledger_integrity(workspace):
    config = _config(workspace, "restart-session")

    first = BrAInKRuntime(config)
    first.start()
    first.process_command("run diagnostics")
    shutdown = first.shutdown(clean=True)
    entries_before = shutdown["last_entry_id"]
    head_before = shutdown["last_entry_hash"]

    second = BrAInKRuntime(config)
    manager = RestartManager(
        config["state_path"], config["ledger_path"], session_id="restart-session"
    )
    report = manager.recover(second.ledger)
    assert report["state_found"] is True
    assert report["clean_shutdown"] is True
    assert report["chain_valid"] is True
    assert report["saved_entry_hash"] == head_before

    resumed = second.start()
    assert resumed["entry_id"] == entries_before + 1
    assert second.ledger.verify_chain() is True

    receipt = second.ledger.export_receipt()
    assert receipt["chain_valid"] is True
    assert receipt["entry_count"] == entries_before + 1
    second.shutdown(clean=True)


def test_end_to_end_proof_receipt(workspace):
    config = _config(workspace, "proof-session")
    runtime = BrAInKRuntime(config)
    runtime.start()
    runtime.process_command("run diagnostics")
    runtime.process_command("status")
    ledger_receipt = runtime.ledger.export_receipt()
    runtime.shutdown(clean=True)

    reopened = Ledger(config["ledger_path"])
    try:
        manager = RestartManager(
            config["state_path"], config["ledger_path"], session_id="proof-session"
        )
        restart_receipt = manager.generate_restart_receipt(
            reopened, manager.load_state()
        )
    finally:
        reopened.close()

    proof = generate_validation_receipt(
        component_id=runtime.runtime_id,
        status="LOCALLY_PROVEN",
        evidence={
            "ledger": ledger_receipt,
            "restart": restart_receipt,
            "dns_status_cap": "LOCALLY_EXECUTED",
            "production_signer": "DEFINED",
        },
    )
    assert proof["receipt_type"] == "VALIDATION_RECEIPT"
    assert proof["status"] == "LOCALLY_PROVEN"
    assert len(proof["receipt_hash"]) == 64
    assert proof["evidence"]["ledger"]["chain_valid"] is True
    assert proof["evidence"]["restart"]["continuity_proven"] is True

    envelope = TestSigner().sign(proof)
    assert TestSigner().verify(envelope, proof) is True


def test_package_manifest_generation(workspace):
    src = os.path.join(workspace, "pkg", "sub")
    os.makedirs(src)
    with open(os.path.join(workspace, "pkg", "a.txt"), "w", encoding="utf-8") as handle:
        handle.write("alpha")
    with open(os.path.join(src, "b.txt"), "w", encoding="utf-8") as handle:
        handle.write("beta")

    manifest = generate_package_manifest(os.path.join(workspace, "pkg"))
    assert manifest["file_count"] == 2
    assert set(manifest["files"]) == {"a.txt", "sub/b.txt"}
    assert all(len(h) == 64 for h in manifest["files"].values())
    assert len(manifest["manifest_hash"]) == 64
    assert manifest["hash_algorithm"] == "sha256"

    again = generate_package_manifest(os.path.join(workspace, "pkg"))
    assert again["manifest_hash"] == manifest["manifest_hash"]


def test_package_manifest_rejects_bad_root():
    with pytest.raises(ValueError):
        generate_package_manifest("/definitely/not/a/real/path")


def test_generate_test_results_status():
    passed = generate_test_results(10, 0, 0, ["t1", "t2"], raw_summary="10 passed")
    assert passed["status"] == "PASSED"
    assert passed["tests_run"] == 10

    failed = generate_test_results(8, 2, 0, ["t1"])
    assert failed["status"] == "FAILED"
    assert failed["tests_run"] == 10


def test_generate_validation_receipt_requires_fields():
    with pytest.raises(ValueError):
        generate_validation_receipt("", "LOCALLY_PROVEN", {})
    with pytest.raises(ValueError):
        generate_validation_receipt("abc", "", {})
