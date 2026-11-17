"""R20: escaped unpaired Unicode surrogate must fail closed on ledger readback.

Architect: A. Keddeh. Original V4 source and historical schema are unchanged.
"""
import json

import pytest

from runtime.illlm_ledger import ILLLMImmutableLedger


def _seed(ledger):
    return ledger.append(
        source_uri="braink://tests/unicode", source_level="TEST",
        semantic_type="GENERIC_EVENT", correlation_id="unicode-r20",
        payload={"message": "ordinary"}, lexical_state={"l": 1},
        illlm_state={"i": 1},
    )


def test_escaped_unpaired_surrogate_returns_failure_instead_of_throwing(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    _seed(ledger)
    event = json.loads(ledger.path.read_text(encoding="utf-8"))
    event["payload"]["message"] = "\ud800"
    ledger.path.write_bytes((json.dumps(event, ensure_ascii=True) + "\n").encode("utf-8"))
    result = ledger.verify()
    assert result["status"] == "FAILED"
    assert result["reason"] == "UNENCODABLE_LEDGER_RECORD"


def test_surrogate_corruption_blocks_append_without_modifying_file(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    _seed(ledger)
    event = json.loads(ledger.path.read_text(encoding="utf-8"))
    event["payload"]["message"] = "\udfff"
    ledger.path.write_bytes((json.dumps(event, ensure_ascii=True) + "\n").encode("utf-8"))
    before = ledger.path.read_bytes()
    with pytest.raises(RuntimeError, match="ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND"):
        ledger.append(source_uri="braink://tests/unicode", source_level="TEST",
                      semantic_type="GENERIC_EVENT", correlation_id="next",
                      payload={"message": "next"}, lexical_state={}, illlm_state={})
    assert ledger.path.read_bytes() == before


def test_valid_unicode_and_escaped_serialization_remain_compatible(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    ledger.append(source_uri="braink://tests/unicode", source_level="TEST",
                  semantic_type="GENERIC_EVENT", correlation_id="valid-unicode",
                  payload={"message": "Café Ω 🌍"}, lexical_state={}, illlm_state={})
    assert ledger.verify()["status"] == "PASS"
    event = json.loads(ledger.path.read_text(encoding="utf-8"))
    ledger.path.write_bytes((json.dumps(event, ensure_ascii=True) + "\n").encode("utf-8"))
    assert ledger.verify()["status"] == "PASS"
