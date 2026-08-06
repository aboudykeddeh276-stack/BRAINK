import pytest

from braink_runtime.signer import (
    ProductionSignerPlaceholder,
    SignatureEnvelope,
    TestSigner,
    prepare_canonical_payload,
)


@pytest.fixture()
def signer():
    return TestSigner()


def test_sign_returns_envelope(signer):
    envelope = signer.sign({"a": 1})
    assert isinstance(envelope, SignatureEnvelope)
    assert envelope.algorithm == "HMAC-SHA256"
    assert len(envelope.signature) == 64
    assert len(envelope.payload_hash) == 64
    assert envelope.verified is True
    assert envelope.key_id == signer.key_id


def test_verify_true_for_valid_signature(signer):
    payload = {"intent": "EXECUTE", "n": 3}
    assert signer.verify(signer.sign(payload), payload) is True


def test_verify_false_for_tampered_payload(signer):
    payload = {"intent": "EXECUTE"}
    envelope = signer.sign(payload)
    assert signer.verify(envelope, {"intent": "HALT"}) is False


def test_verify_false_for_tampered_signature(signer):
    payload = {"intent": "EXECUTE"}
    envelope = signer.sign(payload)
    envelope.signature = "0" * 64
    assert signer.verify(envelope, payload) is False


def test_verify_false_for_wrong_key(signer):
    payload = {"intent": "EXECUTE"}
    envelope = signer.sign(payload)
    other = TestSigner(key=b"another-test-only-key", key_id="test-key-local-0002")
    assert other.verify(envelope, payload) is False


def test_verify_false_for_wrong_algorithm(signer):
    payload = {"a": 1}
    envelope = signer.sign(payload)
    envelope.algorithm = "NONE"
    assert signer.verify(envelope, payload) is False


def test_verify_handles_none(signer):
    assert signer.verify(None, {"a": 1}) is False
    assert signer.verify(signer.sign({"a": 1}), None) is False


def test_sign_rejects_non_dict(signer):
    with pytest.raises(ValueError):
        signer.sign("not a dict")


def test_signature_is_deterministic(signer):
    assert signer.sign({"a": 1, "b": 2}).signature == signer.sign({"b": 2, "a": 1}).signature


def test_envelope_to_dict(signer):
    data = signer.sign({"a": 1}).to_dict()
    assert set(data) == {
        "payload_hash",
        "key_id",
        "algorithm",
        "signature",
        "verified",
    }


def test_prepare_canonical_payload_deterministic():
    assert prepare_canonical_payload({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_test_signer_trust_level(signer):
    assert signer.trust_level == "LOCALLY_PROVEN"


def test_production_signer_sign_raises():
    placeholder = ProductionSignerPlaceholder()
    with pytest.raises(NotImplementedError) as excinfo:
        placeholder.sign({"a": 1})
    assert "Production signer not configured" in str(excinfo.value)


def test_production_signer_verify_raises():
    placeholder = ProductionSignerPlaceholder()
    with pytest.raises(NotImplementedError):
        placeholder.verify(None, {"a": 1})


def test_production_signer_is_defined_not_validated():
    placeholder = ProductionSignerPlaceholder()
    assert placeholder.trust_level == "DEFINED"
    assert placeholder.trust_level != "PRODUCTION_VALIDATED"


def test_production_signer_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("BRAINK_SIGNER_KEY", raising=False)
    assert ProductionSignerPlaceholder().is_configured() is False
