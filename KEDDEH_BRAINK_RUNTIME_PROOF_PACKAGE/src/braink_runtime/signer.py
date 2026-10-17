"""Signing boundary.

Two implementations live here:

* :class:`TestSigner` - HMAC-SHA256 over the canonical payload with a **public,
  non-secret, test-only** key. Status: LOCALLY_PROVEN.
* :class:`ProductionSignerPlaceholder` - the shape of the production signer.
  It deliberately raises so that no code path can silently believe it produced
  a production-grade signature. Status: DEFINED.

No real private key or production secret is present in this file, and none may
ever be added to it.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any, Dict

from .canonical import canonical_hash, canonical_serialize

__all__ = [
    "SignatureEnvelope",
    "TestSigner",
    "ProductionSignerPlaceholder",
    "prepare_canonical_payload",
    "TEST_KEY_ID",
]

# NOT A SECRET. Test-only key material, published deliberately so that the
# HMAC path can be proven locally. Never use for anything real.
_TEST_ONLY_KEY = b"BRAINK-TEST-ONLY-KEY-NOT-A-SECRET"
TEST_KEY_ID = "test-key-local-0001"


@dataclass
class SignatureEnvelope:
    payload_hash: str
    key_id: str
    algorithm: str
    signature: str
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload_hash": self.payload_hash,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "signature": self.signature,
            "verified": self.verified,
        }


def prepare_canonical_payload(payload: Dict[str, Any]) -> str:
    """Canonical string that is actually signed. Deterministic by construction."""
    return canonical_serialize(payload)


class TestSigner:
    """HMAC-SHA256 signer using a published test key. LOCALLY_PROVEN."""

    algorithm = "HMAC-SHA256"
    trust_level = "LOCALLY_PROVEN"
    __test__ = False  # not a pytest test class

    def __init__(self, key: bytes = _TEST_ONLY_KEY, key_id: str = TEST_KEY_ID) -> None:
        if not isinstance(key, (bytes, bytearray)):
            raise ValueError("key must be bytes")
        self._key = bytes(key)
        self.key_id = key_id

    def _mac(self, payload: Dict[str, Any]) -> str:
        message = prepare_canonical_payload(payload).encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def sign(self, payload: Dict[str, Any]) -> SignatureEnvelope:
        if payload is None or not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        return SignatureEnvelope(
            payload_hash=canonical_hash(payload),
            key_id=self.key_id,
            algorithm=self.algorithm,
            signature=self._mac(payload),
            verified=True,
        )

    def verify(self, envelope: SignatureEnvelope, payload: Dict[str, Any]) -> bool:
        if envelope is None or payload is None:
            return False
        if envelope.algorithm != self.algorithm:
            return False
        if envelope.key_id != self.key_id:
            return False
        if envelope.payload_hash != canonical_hash(payload):
            return False
        return hmac.compare_digest(envelope.signature, self._mac(payload))


class ProductionSignerPlaceholder:
    """Interface-complete, intentionally unimplemented production signer.

    Status: DEFINED. It cannot become PRODUCTION_VALIDATED until real key
    infrastructure (HSM / KMS / hardware token) is wired in and independently
    attested outside this package.
    """

    algorithm = "ED25519-OR-KMS-BACKED"
    trust_level = "DEFINED"
    _MESSAGE = "Production signer not configured. Provide key via environment."

    def __init__(self, key_env_var: str = "BRAINK_SIGNER_KEY") -> None:
        self.key_env_var = key_env_var
        self.key_id = "production-key-unconfigured"

    def is_configured(self) -> bool:
        return bool(os.environ.get(self.key_env_var))

    def sign(self, payload: Dict[str, Any]) -> SignatureEnvelope:
        raise NotImplementedError(self._MESSAGE)

    def verify(self, envelope: SignatureEnvelope, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError(self._MESSAGE)
