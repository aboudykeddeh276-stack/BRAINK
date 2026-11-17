"""R18: reject JSON numeric exponent overflow without an uncaught verifier exception.

Architect A. Keddeh, KS-BRAINK-IL-LLM. Uses actual filesystem bytes.
"""
import pytest
from runtime.illlm_ledger import ILLLMImmutableLedger


def _args(correlation):
    return dict(source_uri='braink://generic/event', source_level='UNQUALIFIED',
                semantic_type='GENERIC_EVENT', correlation_id=correlation,
                payload={'value': 'ordinary'}, lexical_state={'value': 'fixed'},
                illlm_state={'value': 'fixed'})


@pytest.mark.parametrize('numeric', ['1e400', '-1e400', '1e99999'])
def test_exponent_overflow_fails_closed_without_throwing_or_appending(tmp_path, numeric):
    ledger = ILLLMImmutableLedger(tmp_path / 'ledger.jsonl')
    ledger.append(**_args('first'))
    raw = ledger.path.read_bytes()
    assert b'"ordinary"' in raw
    tampered = raw.replace(b'"ordinary"', numeric.encode('ascii'), 1)
    ledger.path.write_bytes(tampered)
    result = ledger.verify()
    assert result['status'] == 'FAILED', result
    with pytest.raises(RuntimeError, match='ILLLM_LEDGER_UNVERIFIED_BEFORE_APPEND'):
        ledger.append(**_args('second'))
    assert ledger.path.read_bytes() == tampered


def test_finite_exponent_serialization_preserves_historical_hash(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / 'ledger.jsonl')
    args = _args('finite')
    args['payload'] = {'value': 1000.0}
    ledger.append(**args)
    raw = ledger.path.read_bytes()
    assert b'1000.0' in raw
    ledger.path.write_bytes(raw.replace(b'1000.0', b'1e3', 1))
    result = ledger.verify()
    assert result['status'] == 'PASS', result
    assert result['events'] == 1
