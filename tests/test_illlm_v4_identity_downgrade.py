"""V4 identity downgrade must not bypass resident semantic checks.

Architect: A. Keddeh / KS-BRAINK-IL-LLM. Physical ledger file test.
"""
import json
import pytest
from runtime.illlm_ledger import ILLLMImmutableLedger, root
from tests.test_illlm_semantic_preappend import candidate


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
