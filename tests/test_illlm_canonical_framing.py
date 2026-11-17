"""Resident JSONL evidence must reject ambiguous physical records.

Architect: A. Keddeh / KS-BRAINK-IL-LLM.
"""
import json
import pytest
from runtime.illlm_ledger import ILLLMImmutableLedger


def _args(correlation):
    return dict(source_uri="braink://generic/event", source_level="UNQUALIFIED",
                semantic_type="GENERIC_EVENT", correlation_id=correlation,
                payload={"value": correlation}, lexical_state={"value": correlation},
                illlm_state={"value": correlation})


@pytest.mark.parametrize("mutation", ["blank", "duplicate_key", "nested_duplicate_key"])
def test_ambiguous_disk_record_fails_closed_before_append(tmp_path, mutation):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    ledger.append(**_args("first"))
    original = ledger.path.read_bytes()
    assert original.endswith(b"\n")
    if mutation == "blank":
        tampered = original + b"\n"
    elif mutation == "duplicate_key":
        # Python's json.loads silently retains the last occurrence.
        tampered = original.replace(b'{"correlation_id":', b'{"schema":"bogus","correlation_id":', 1)
    elif mutation == "nested_duplicate_key":
        tampered = original.replace(b'"payload":{"value":"first"}',
                                    b'"payload":{"value":"bogus","value":"first"}', 1)
    assert tampered != original
    ledger.path.write_bytes(tampered)
    result = ledger.verify()
    assert result["status"] == "FAILED", result
    with pytest.raises(RuntimeError, match="ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND"):
        ledger.append(**_args("second"))
    assert ledger.path.read_bytes() == tampered


def test_canonical_disk_records_survive_reopen(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ILLLMImmutableLedger(path)
    ledger.append(**_args("first"))
    ledger.append(**_args("second"))
    reopened = ILLLMImmutableLedger(path)
    assert reopened.verify()["events"] == 2


def test_legacy_valid_json_serialization_remains_readable(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    ledger.append(**_args("first"))
    event = json.loads(ledger.path.read_text())
    ledger.path.write_text(json.dumps(event, sort_keys=True, ensure_ascii=True) + "\n")
    assert ledger.verify()["events"] == 1
