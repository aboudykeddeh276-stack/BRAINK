import json
import os
import shutil
import tempfile

import pytest

from braink_runtime.ledger import Ledger
from braink_runtime.restart import RestartManager, RestartState


@pytest.fixture()
def workspace():
    path = tempfile.mkdtemp(prefix="braink-restart-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def paths(workspace):
    return (
        os.path.join(workspace, "ledger.sqlite"),
        os.path.join(workspace, "restart_state.json"),
    )


def test_save_state_writes_file(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    ledger.append("START", {})
    manager = RestartManager(state_path, ledger_path, session_id="session-1")
    state = manager.save_state(ledger, clean=True)
    ledger.close()

    assert os.path.exists(state_path)
    with open(state_path, encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["session_id"] == "session-1"
    assert data["last_entry_id"] == 1
    assert data["clean_shutdown"] is True
    assert state.last_entry_hash == data["last_entry_hash"]


def test_load_state_round_trip(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    ledger.append("START", {})
    manager = RestartManager(state_path, ledger_path, session_id="session-2")
    saved = manager.save_state(ledger)
    ledger.close()

    loaded = RestartManager(state_path, ledger_path).load_state()
    assert isinstance(loaded, RestartState)
    assert loaded.to_dict() == saved.to_dict()


def test_load_state_missing_returns_none(paths):
    ledger_path, state_path = paths
    assert RestartManager(state_path, ledger_path).load_state() is None


def test_load_state_corrupt_returns_none(paths):
    ledger_path, state_path = paths
    with open(state_path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    assert RestartManager(state_path, ledger_path).load_state() is None


def test_recover_reopens_and_verifies(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    for i in range(3):
        ledger.append("EVENT", {"i": i})
    manager = RestartManager(state_path, ledger_path, session_id="session-3")
    manager.save_state(ledger, clean=True)
    ledger.close()

    reopened = Ledger(ledger_path)
    try:
        report = RestartManager(state_path, ledger_path, session_id="session-3").recover(
            reopened
        )
        assert report["state_found"] is True
        assert report["clean_shutdown"] is True
        assert report["chain_valid"] is True
        assert report["tampered_entries"] == []
        assert report["recovery_ok"] is True
        assert report["current_entry_id"] == 3
        assert report["entries_since_saved_state"] == 0
        assert report["status"] == "RESTART_TESTED"
    finally:
        reopened.close()


def test_simulate_unclean_shutdown_appends_crash_event(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    ledger.append("START", {})
    manager = RestartManager(state_path, ledger_path, session_id="session-4")
    manager.save_state(ledger, clean=True)
    entry = manager.simulate_unclean_shutdown(ledger)
    ledger.close()

    assert entry["event_type"] == "CRASH_SIMULATED"

    reopened = Ledger(ledger_path)
    try:
        types = [e.event_type for e in reopened.get_all()]
        assert "CRASH_SIMULATED" in types
        report = manager.recover(reopened)
        assert report["chain_valid"] is True
        assert report["entries_since_saved_state"] == 1
    finally:
        reopened.close()


def test_post_restart_integrity_after_crash(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    ledger.append("START", {})
    manager = RestartManager(state_path, ledger_path, session_id="session-5")
    manager.save_state(ledger, clean=True)
    manager.simulate_unclean_shutdown(ledger)
    ledger.close()

    reopened = Ledger(ledger_path)
    try:
        assert reopened.verify_chain() is True
        assert reopened.detect_tamper() == []
        resumed = reopened.append("RESUMED", {})
        assert resumed.entry_id == 3
        assert reopened.verify_chain() is True
    finally:
        reopened.close()


def test_restart_receipt_fields(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    ledger.append("START", {})
    manager = RestartManager(state_path, ledger_path, session_id="session-6")
    state = manager.save_state(ledger, clean=True)
    ledger.close()

    reopened = Ledger(ledger_path)
    try:
        receipt = manager.generate_restart_receipt(reopened, state)
    finally:
        reopened.close()

    required = {
        "receipt_type",
        "session_id",
        "ledger_path",
        "state_path",
        "pre_restart_state",
        "post_restart_entry_id",
        "post_restart_entry_hash",
        "entry_count",
        "chain_valid",
        "tampered_entries",
        "recovery_report",
        "continuity_proven",
        "generated_at",
        "status",
    }
    assert required.issubset(set(receipt))
    assert receipt["receipt_type"] == "RESTART_PROOF"
    assert receipt["continuity_proven"] is True
    assert receipt["status"] == "RESTART_TESTED"
    assert receipt["post_restart_entry_hash"] == state.last_entry_hash


def test_recover_without_state(paths):
    ledger_path, state_path = paths
    ledger = Ledger(ledger_path)
    ledger.append("START", {})
    try:
        report = RestartManager(state_path, ledger_path).recover(ledger)
        assert report["state_found"] is False
        assert report["clean_shutdown"] is False
        assert report["chain_valid"] is True
    finally:
        ledger.close()


def test_manager_requires_paths():
    with pytest.raises(ValueError):
        RestartManager("", "ledger.sqlite")
    with pytest.raises(ValueError):
        RestartManager("state.json", "")
