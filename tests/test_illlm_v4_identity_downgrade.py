"""V4 identity downgrade must not bypass resident semantic checks.

Architect: A. Keddeh / KS-BRAINK-IL-LLM. Physical ledger file test.
"""
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



def downgraded_fields():
    return {
        'source_level': 'UNQUALIFIED',
        'semantic_type': 'GENERIC_EVENT',
        'source_uri': 'braink://generic/event',
    }


def test_v4_shaped_payload_cannot_be_appended_with_downgraded_identity(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / 'ledger.jsonl')
    args = candidate()
    args.update(downgraded_fields())
    with pytest.raises(ValueError, match='SEMANTIC_V4_'):
        ledger.append(**args)
    assert ledger.verify()['events'] == 0


def test_v4_identity_downgrade_with_recomputed_chain_is_rejected(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / 'ledger.jsonl')
    ledger.append(**candidate())
    event = json.loads(ledger.path.read_text().splitlines()[0])
    event.update(downgraded_fields())
    event['event_id'] = root({
        'correlation_id': event['correlation_id'],
        'source_uri': event['source_uri'],
        'semantic_type': event['semantic_type'],
        'illlm_root': event['illlm_root'],
    })
    event['event_root'] = root({k: v for k, v in event.items() if k != 'event_root'})
    ledger.path.write_text(json.dumps(event, sort_keys=True, separators=(',', ':')) + '\n')
    result = ledger.verify()
    assert result['status'] == 'FAILED', result
    assert result['reason'].startswith('SEMANTIC_V4_'), result


def test_unrelated_event_family_with_state_remains_admissible(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / 'generic.jsonl')
    event = ledger.append(
        source_uri='braink://generic/event',
        source_level='UNQUALIFIED',
        semantic_type='GENERIC_EVENT',
        correlation_id='generic-001',
        payload={'state': {'unrelated': 'value'}, 'sequence': 1},
        lexical_state={'term': 'generic'},
        illlm_state={'term': 'generic'},
    )
    assert ledger.verify() == {'status': 'PASS', 'events': 1, 'head': event.event_root}
