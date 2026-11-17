"""V4 receipt-stripping and identity-downgrade falsification.

Architect: A. Keddeh / KS-BRAINK-IL-LLM.
Checks actual JSONL persistence and the resident admission path.
"""
import json

import pytest

from runtime.illlm_ledger import ILLLMImmutableLedger, root
from test_illlm_v4_identity_downgrade import candidate, downgraded_fields


def _strip_receipt(args):
    args["payload"]["state"].pop("v4_receipt")
    args["payload"]["candidate_hash"] = root(args["payload"]["state"])
    return args


def test_receipt_stripped_v4_shape_rejected_before_disk_append(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "append.jsonl")
    args = _strip_receipt(candidate())
    args.update(downgraded_fields())
    with pytest.raises(ValueError, match="SEMANTIC_V4_"):
        ledger.append(**args)
    assert ledger.verify() == {"status": "PASS", "events": 0, "head": "GENESIS"}
    assert not ledger.path.exists() or ledger.path.stat().st_size == 0


def test_receipt_stripped_v4_rehashed_history_rejected(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "history.jsonl")
    ledger.append(**candidate())
    event = json.loads(ledger.path.read_text().splitlines()[0])
    event["payload"]["state"].pop("v4_receipt")
    event["payload"]["candidate_hash"] = root(event["payload"]["state"])
    event.update(downgraded_fields())
    event["event_id"] = root({
        "correlation_id": event["correlation_id"],
        "source_uri": event["source_uri"],
        "semantic_type": event["semantic_type"],
        "illlm_root": event["illlm_root"],
    })
    event["event_root"] = root({k: v for k, v in event.items() if k != "event_root"})
    ledger.path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    result = ledger.verify()
    assert result["status"] == "FAILED", result
    assert result["reason"].startswith("SEMANTIC_V4_"), result


def test_generic_unrelated_state_and_payload_not_reclassified(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "generic.jsonl")
    event = ledger.append(
        source_uri="braink://generic/event", source_level="UNQUALIFIED",
        semantic_type="GENERIC_EVENT", correlation_id="generic-unrelated-001",
        payload={"state": {"observer": "non-V4"}, "candidate_hash": "generic"},
        lexical_state={"term": "generic"}, illlm_state={"term": "generic"},
    )
    assert ledger.verify() == {"status": "PASS", "events": 1, "head": event.event_root}
