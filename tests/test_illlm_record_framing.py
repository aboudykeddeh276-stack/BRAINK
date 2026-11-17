"""Fail-closed JSONL framing across resident interprocess append boundaries.

Architect: A. Keddeh / KS-BRAINK-IL-LLM.
"""
import pytest
from runtime.illlm_ledger import ILLLMImmutableLedger


def event_args(correlation):
    return {
        "source_uri": "braink://generic/event",
        "source_level": "UNQUALIFIED",
        "semantic_type": "GENERIC_EVENT",
        "correlation_id": correlation,
        "payload": {"value": correlation},
        "lexical_state": {"value": correlation},
        "illlm_state": {"value": correlation},
    }


def test_missing_final_newline_is_rejected_before_second_append(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    ledger.append(**event_args("first"))
    original = ledger.path.read_bytes()
    assert original.endswith(b"\n")
    unterminated = original[:-1]
    ledger.path.write_bytes(unterminated)
    result = ledger.verify()
    assert result == {"status": "FAILED", "reason": "UNTERMINATED_LEDGER_RECORD", "index": 0}
    with pytest.raises(RuntimeError, match="ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND"):
        ledger.append(**event_args("second"))
    assert ledger.path.read_bytes() == unterminated


def test_terminated_and_empty_ledgers_remain_compatible(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    assert ledger.verify()["status"] == "PASS"
    first = ledger.append(**event_args("first"))
    second = ledger.append(**event_args("second"))
    assert ledger.verify() == {"status": "PASS", "events": 2, "head": second.event_root}
    assert ledger.path.read_bytes().endswith(b"\n")
