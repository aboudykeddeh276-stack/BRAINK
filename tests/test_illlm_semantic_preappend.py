"""Fail-closed resident IL-LLM admission regressions.

Architect: A. Keddeh / KS-BRAINK-IL-LLM. Uses real filesystem I/O.
"""
import hashlib
import json

import pytest

from runtime.illlm_ledger import ILLLMImmutableLedger, root


def candidate(*, sequence=1, policy=None, receipt_id="R9-001"):
    state = {
        "instance_id": "resident-r9-admission-001",
        "source_sha256": "3cf4c7713e2fa4e38cfba840336854b3e488c899c35fd27e7a21e376b910b1d3",
        "observer": {"wholeIdentity": "1_BRAINK", "stateFormula": "O_AS_OBS=1_O⊗S_O(E)"},
        "polygon": {"iteration": 1},
        "v4_receipt": {"id": receipt_id, "type": "POLYGON_100_ITERATION", "iteration": 1},
    }
    candidate_hash = root(state)
    return {
        "source_uri": f"braink://learning/v4/browser/{state['instance_id']}",
        "source_level": "OBSERVER_MIRROR_ONLY",
        "semantic_type": "POLYGON_MIRROR_CANDIDATE",
        "correlation_id": root({"instance_id": state["instance_id"], "v4_receipt_id": state["v4_receipt"]["id"], "source_sha256": state["source_sha256"]}),
        "payload": {
            "candidate_hash": candidate_hash,
            "sequence": sequence,
            "observer_policy_digest": policy if policy is not None else root({"candidate_must_be_mirror_only": True, "resident_capability_required": True}),
            "state": state,
            "promotion_state": "NOT_PROMOTED",
        },
        "lexical_state": {"source": "V4", "receipt": state["v4_receipt"], "polygon_lexical_context": state["polygon"]},
        "illlm_state": {"candidate": candidate_hash, "observer": state["observer"], "source": state["source_sha256"], "authority": "MIRROR_ONLY"},
        "idempotency_payload_field": "candidate_hash",
    }


def test_invalid_v4_cannot_poison_empty_ledger(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "illlm.jsonl")
    with pytest.raises(ValueError, match="SEMANTIC_V4_ADMISSION_POLICY"):
        ledger.append(**candidate(policy="0" * 64))
    assert ledger.verify() == {"status": "PASS", "events": 0, "head": "GENESIS"}
    assert not ledger.path.exists() or ledger.path.stat().st_size == 0


def test_invalid_v4_cannot_poison_valid_ledger(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "illlm.jsonl")
    first = ledger.append(**candidate())
    before = ledger.path.read_bytes()
    with pytest.raises(ValueError, match="SEMANTIC_V4_ADMISSION_POLICY"):
        ledger.append(**candidate(policy="0" * 64, sequence=2, receipt_id="R9-002"))
    assert ledger.path.read_bytes() == before
    assert ledger.verify() == {"status": "PASS", "events": 1, "head": first.event_root}


def test_same_correlation_modified_payload_rejected_without_write(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "illlm.jsonl")
    first = ledger.append(**candidate())
    before = ledger.path.read_bytes()
    with pytest.raises(ValueError, match="CORRELATION_REPLAY_CONFLICT"):
        ledger.append(**candidate(sequence=2))
    assert ledger.path.read_bytes() == before
    assert ledger.verify() == {"status": "PASS", "events": 1, "head": first.event_root}


def test_identical_replay_remains_idempotent(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "illlm.jsonl")
    first = ledger.append(**candidate())
    before = ledger.path.read_bytes()
    again = ledger.append(**candidate())
    assert again == first
    assert ledger.path.read_bytes() == before
