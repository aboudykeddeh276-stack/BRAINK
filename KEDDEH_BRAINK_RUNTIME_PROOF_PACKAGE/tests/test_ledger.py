import os
import shutil
import sqlite3
import tempfile

import pytest

from braink_runtime.ledger import GENESIS_HASH, Ledger


@pytest.fixture()
def workspace():
    path = tempfile.mkdtemp(prefix="braink-ledger-")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def ledger(workspace):
    instance = Ledger(os.path.join(workspace, "ledger.sqlite"))
    try:
        yield instance
    finally:
        try:
            instance.close()
        except sqlite3.ProgrammingError:
            pass


def test_append_creates_entry_with_genesis_prev(ledger):
    entry = ledger.append("START", {"a": 1})
    assert entry.entry_id == 1
    assert entry.prev_hash == GENESIS_HASH
    assert entry.entry_hash == entry.compute_hash()
    assert len(entry.entry_hash) == 64


def test_chain_links_successive_entries(ledger):
    first = ledger.append("START", {})
    second = ledger.append("COMMAND", {"intent": "EXECUTE"})
    assert second.prev_hash == first.entry_hash
    assert second.entry_id == 2


def test_verify_chain_passes_on_good_ledger(ledger):
    for i in range(5):
        ledger.append("EVENT", {"i": i})
    assert ledger.verify_chain() is True


def test_detect_tamper_empty_on_good_ledger(ledger):
    ledger.append("EVENT", {"i": 1})
    ledger.append("EVENT", {"i": 2})
    assert ledger.detect_tamper() == []


def test_empty_ledger_is_valid(ledger):
    assert ledger.verify_chain() is True
    assert ledger.count() == 0
    assert ledger.head_hash() == GENESIS_HASH
    assert ledger.head_id() == 0


def test_get_all_and_get(ledger):
    ledger.append("A", {"x": 1})
    ledger.append("B", {"x": 2})
    entries = ledger.get_all()
    assert [e.event_type for e in entries] == ["A", "B"]
    assert ledger.get(2).payload == {"x": 2}
    assert ledger.get(99) is None


def test_tampered_payload_is_detected(workspace):
    path = os.path.join(workspace, "tamper.sqlite")
    ledger = Ledger(path)
    ledger.append("EVENT", {"value": "original"})
    ledger.append("EVENT", {"value": "second"})
    ledger.close()

    conn = sqlite3.connect(path)
    conn.execute(
        'UPDATE ledger SET payload = ? WHERE entry_id = 1',
        ('{"value":"TAMPERED"}',),
    )
    conn.commit()
    conn.close()

    reopened = Ledger(path)
    try:
        assert reopened.verify_chain() is False
        assert 1 in reopened.detect_tamper()
    finally:
        reopened.close()


def test_tampered_hash_is_detected(workspace):
    path = os.path.join(workspace, "tamper2.sqlite")
    ledger = Ledger(path)
    ledger.append("EVENT", {"value": 1})
    ledger.close()

    conn = sqlite3.connect(path)
    conn.execute('UPDATE ledger SET entry_hash = ? WHERE entry_id = 1', ("0" * 64,))
    conn.commit()
    conn.close()

    reopened = Ledger(path)
    try:
        assert reopened.detect_tamper() == [1]
    finally:
        reopened.close()


def test_reopen_continues_chain(workspace):
    path = os.path.join(workspace, "reopen.sqlite")
    first = Ledger(path)
    first.append("A", {})
    second_entry = first.append("B", {})
    first.close()

    reopened = Ledger(path)
    try:
        third = reopened.append("C", {})
        assert third.entry_id == 3
        assert third.prev_hash == second_entry.entry_hash
        assert reopened.verify_chain() is True
    finally:
        reopened.close()


def test_export_receipt_structure(ledger):
    ledger.append("A", {})
    ledger.append("B", {})
    receipt = ledger.export_receipt()
    assert receipt["receipt_type"] == "LEDGER_INTEGRITY"
    assert receipt["entry_count"] == 2
    assert receipt["genesis_hash"] == GENESIS_HASH
    assert receipt["root_hash"] == ledger.get_all()[-1].entry_hash
    assert len(receipt["hashes"]) == 2
    assert receipt["chain_valid"] is True
    assert receipt["tampered_entries"] == []
    assert receipt["status"] == "LOCALLY_PROVEN"


def test_duplicate_events_get_distinct_hashes(ledger):
    a = ledger.append("DUPLICATE", {"same": True})
    b = ledger.append("DUPLICATE", {"same": True})
    assert a.entry_hash != b.entry_hash
    assert b.prev_hash == a.entry_hash
    assert ledger.verify_chain() is True


def test_append_rejects_bad_arguments(ledger):
    with pytest.raises(ValueError):
        ledger.append("", {})
    with pytest.raises(ValueError):
        ledger.append("EVENT", "not-a-dict")


def test_ledger_requires_path():
    with pytest.raises(ValueError):
        Ledger("")


def test_context_manager_closes(workspace):
    path = os.path.join(workspace, "ctx.sqlite")
    with Ledger(path) as instance:
        instance.append("A", {})
    reopened = Ledger(path)
    try:
        assert reopened.count() == 1
    finally:
        reopened.close()
