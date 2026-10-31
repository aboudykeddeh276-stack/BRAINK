"""Reject non-standard JSON numeric constants at append and resident readback.

Architect: A. Keddeh / KS-BRAINK-IL-LLM. Uses real filesystem bytes.
"""
import hashlib
import json

import pytest

from runtime.illlm_ledger import ILLLMImmutableLedger


def _args(correlation, value):
    return dict(source_uri="braink://generic/event", source_level="UNQUALIFIED",
                semantic_type="GENERIC_EVENT", correlation_id=correlation,
                payload={"value": value}, lexical_state={"value": "fixed"},
                illlm_state={"value": "fixed"})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_append_is_rejected_without_disk_mutation(tmp_path, bad):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    ledger.append(**_args("first", "ordinary"))
    before = ledger.path.read_bytes()
    with pytest.raises(ValueError):
        ledger.append(**_args("second", bad))
    assert ledger.path.read_bytes() == before
    assert ledger.verify()["status"] == "PASS"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_rehashed_nonfinite_disk_record_is_rejected(tmp_path, bad):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    ledger.append(**_args("first", "ordinary"))
    event = json.loads(ledger.path.read_text())
    event["payload"]["value"] = bad
    # Reconstruct the previously accepted hash with the historical permissive
    # serializer; the repaired canonical serializer must reject nonfinite input.
    old_body = {k: v for k, v in event.items() if k != "event_root"}
    event["event_root"] = hashlib.sha256(json.dumps(
        old_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        default=str).encode("utf-8")).hexdigest()
    tampered = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ledger.path.write_bytes(tampered)
    assert b'NaN' in tampered or b'Infinity' in tampered
    result = ledger.verify()
    assert result["status"] == "FAILED", result
    with pytest.raises(RuntimeError, match="ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND"):
        ledger.append(**_args("second", "ordinary"))
    assert ledger.path.read_bytes() == tampered
