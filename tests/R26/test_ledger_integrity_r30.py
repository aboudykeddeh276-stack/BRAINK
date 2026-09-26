from dataclasses import replace

from runtime.R25.system_evolution_runtime import AppendOnlyLedger


def _ledger_with_two_events() -> AppendOnlyLedger:
    ledger = AppendOnlyLedger()
    ledger.append(
        operation="BOOTSTRAP",
        actor="A",
        owner="A.KEDDEH / KEDDEH_SYSTEMS",
        input_state={"phase": "EMPTY"},
        output_state={"phase": "ROOT_READY"},
        proof={"readback_equal": True},
        rollback={"checkpoint": "root"},
        lineage=["A"],
    )
    ledger.append(
        operation="STATE_WRITE",
        actor="A",
        owner="A.KEDDEH / KEDDEH_SYSTEMS",
        input_state={"phase": "ROOT_READY"},
        output_state={"phase": "CHILD_READY"},
        proof={"readback_equal": True},
        rollback={"checkpoint": "root-ready"},
        lineage=["A"],
    )
    return ledger


def test_ledger_verification_accepts_intact_chain():
    ledger = _ledger_with_two_events()
    assert ledger.verify() is True


def test_ledger_verification_rejects_receipt_payload_tamper():
    ledger = _ledger_with_two_events()
    ledger._events[1] = replace(ledger._events[1], output_hash="0" * 64)
    assert ledger.verify() is False


def test_ledger_verification_rejects_event_reordering():
    ledger = _ledger_with_two_events()
    ledger._events[0], ledger._events[1] = ledger._events[1], ledger._events[0]
    assert ledger.verify() is False


def test_ledger_verification_rejects_event_id_substitution():
    ledger = _ledger_with_two_events()
    ledger._events[1] = replace(ledger._events[1], event_id="f" * 64)
    assert ledger.verify() is False
