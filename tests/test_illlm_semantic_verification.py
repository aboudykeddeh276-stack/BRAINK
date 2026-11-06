"""Real on-disk IL-LLM semantic-root and coherent-rehash falsification tests.

Architect: A. Keddeh. No mock process, external quorum or production claim.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from runtime.illlm_ledger import ILLLMImmutableLedger, root
from runtime.illlm_semantic_validation import semantic_violation


def _state():
    return {
        "instance_id": "resident-v4-test-001",
        "source_sha256": "3cf4c7713e2fa4e38cfba840336854b3e488c899c35fd27e7a21e376b910b1d3",
        "observer": {"wholeIdentity": "1_BRAINK", "stateFormula": "O_AS_OBS=1_O⊗S_O(E)", "queryRoot": "native"},
        "polygon": {"iteration": 1, "lastSuccessor": "①_1", "history_tail": []},
        "v4_receipt": {"id": "R-resident-001", "type": "POLYGON_100_ITERATION", "iteration": 1, "status": "PASS"},
    }


def _append(ledger: ILLLMImmutableLedger):
    state = _state()
    source = state["source_sha256"]
    candidate_hash = root(state)
    return ledger.append(
        source_uri=f"braink://learning/v4/browser/{state['instance_id']}",
        source_level="OBSERVER_MIRROR_ONLY",
        semantic_type="POLYGON_MIRROR_CANDIDATE",
        correlation_id=root({"instance_id": state["instance_id"], "v4_receipt_id": state["v4_receipt"]["id"], "source_sha256": source}),
        payload={"candidate_hash": candidate_hash, "sequence": 1, "observer_policy_digest": root({"candidate_must_be_mirror_only": True, "resident_capability_required": True}), "state": state, "promotion_state": "NOT_PROMOTED"},
        lexical_state={"source": "V4", "receipt": state["v4_receipt"], "polygon_lexical_context": state["polygon"]},
        illlm_state={"candidate": candidate_hash, "observer": state["observer"], "source": source, "authority": "MIRROR_ONLY"},
        idempotency_payload_field="candidate_hash",
    )


def _rewrite(path: Path, event: dict):
    event["event_root"] = root({k: v for k, v in event.items() if k != "event_root"})
    path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def test_native_ledger_accepts_resident_v4_event(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    event = _append(ledger)
    assert ledger.verify() == {"status": "PASS", "events": 1, "head": event.event_root}
    assert semantic_violation(json.loads(ledger.path.read_text()), root) is None


def test_native_ledger_rejects_coherently_rehashed_v4_forgeries(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "ledger.jsonl")
    _append(ledger)
    original = json.loads(ledger.path.read_text())
    cases = {
        "EVENT_ID": lambda e: e.update(event_id="0" * 64),
        "V4_LEXICAL_ROOT": lambda e: e.update(lexical_root="0" * 64),
        "V4_ILLLM_ROOT": lambda e: e.update(illlm_root="0" * 64, event_id=root({"correlation_id": e["correlation_id"], "source_uri": e["source_uri"], "semantic_type": e["semantic_type"], "illlm_root": "0" * 64})),
        "V4_CORRELATION_ID": lambda e: e.update(correlation_id="0" * 64, event_id=root({"correlation_id": "0" * 64, "source_uri": e["source_uri"], "semantic_type": e["semantic_type"], "illlm_root": e["illlm_root"]})),
        "V4_ADMISSION_POLICY": lambda e: e["payload"].update(observer_policy_digest="0" * 64),
        "V4_SOURCE_URI": lambda e: e.update(source_uri="braink://forged", event_id=root({"correlation_id": e["correlation_id"], "source_uri": "braink://forged", "semantic_type": e["semantic_type"], "illlm_root": e["illlm_root"]})),
        "V4_PROMOTION": lambda e: e["payload"].update(promotion_state="PROMOTED"),
        "V4_CANDIDATE_HASH": lambda e: e["payload"].update(candidate_hash="0" * 64),
    }
    for reason, mutation in cases.items():
        forged = copy.deepcopy(original)
        mutation(forged)
        _rewrite(ledger.path, forged)
        result = ledger.verify()
        assert result == {"status": "FAILED", "reason": "SEMANTIC_" + reason, "index": 0}, (reason, result)
        try:
            _append(ledger)
        except RuntimeError as exc:
            assert str(exc) == "ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND"
        else:
            raise AssertionError("CORRUPT_LEDGER_WAS_APPENDABLE")
    _rewrite(ledger.path, original)
    assert ledger.verify()["status"] == "PASS"


def test_native_ledger_preserves_non_v4_events(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "generic.jsonl")
    event = ledger.append(source_uri="braink://generic", source_level="LOCAL", semantic_type="GENERIC", correlation_id="correlation-generic", payload={"x": 1}, lexical_state={"x": 1}, illlm_state={"x": 2})
    assert ledger.verify() == {"status": "PASS", "events": 1, "head": event.event_root}
    forged = json.loads(ledger.path.read_text())
    forged["event_id"] = "0" * 64
    _rewrite(ledger.path, forged)
    assert ledger.verify() == {"status": "FAILED", "reason": "SEMANTIC_EVENT_ID", "index": 0}
