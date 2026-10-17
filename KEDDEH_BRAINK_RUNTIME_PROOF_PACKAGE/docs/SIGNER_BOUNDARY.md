# Signer Boundary

Covers: `src/braink_runtime/signer.py`.
**Status: `TestSigner` = LOCALLY_PROVEN; `ProductionSignerPlaceholder` = DEFINED.**

> **Proof boundary.** The production signer **cannot be PRODUCTION_VALIDATED
> without real key infrastructure.** It has no key, it will never be given one by
> this package, and every one of its methods raises `NotImplementedError`. A
> signer whose key material cannot be independently attested must not claim a
> status above `DEFINED`.

---

## Component identity

`braink:signer` version `1.0.0`. Public names: `SignatureEnvelope`,
`TestSigner`, `ProductionSignerPlaceholder`, `prepare_canonical_payload`,
`TEST_KEY_ID = "test-key-local-0001"`.

## Purpose

Separate two things that are constantly confused: *proving the signing code path
works* and *proving a signature means something*. `TestSigner` does the first
completely. `ProductionSignerPlaceholder` marks where the second would live and
fails closed until it exists.

## Inputs

* `payload: dict` — a non-dict raises `ValueError` in `TestSigner.sign`.
* `envelope: SignatureEnvelope` plus the payload, for verification.
* Optional `key: bytes` and `key_id: str` for `TestSigner`; optional
  `key_env_var` (default `BRAINK_SIGNER_KEY`) for the placeholder.

## Outputs

`SignatureEnvelope(payload_hash, key_id, algorithm, signature, verified)` and its
`to_dict()`; a `bool` from `verify`; `NotImplementedError` from every production
method.

## Dependencies

Stdlib `hmac`, `hashlib`, `os`, `dataclasses`; `braink_runtime.canonical`.

## Interfaces

```python
signer   = TestSigner()
envelope = signer.sign({"intent": "EXECUTE"})
signer.verify(envelope, {"intent": "EXECUTE"})   # True
signer.verify(envelope, {"intent": "HALT"})      # False

prod = ProductionSignerPlaceholder()
prod.is_configured()        # False unless BRAINK_SIGNER_KEY is set
prod.sign({"a": 1})         # raises NotImplementedError
prepare_canonical_payload({"b": 1, "a": 2})      # '{"a":2,"b":1}'
```

## Reconstruction rules

1. **What is signed.** `prepare_canonical_payload(payload)` returns
   `canonical_serialize(payload)`. The MAC is computed over the UTF-8 encoding of
   that string. Signing canonical bytes rather than a Python `repr` is what makes
   a signature portable and reproducible.
2. **`TestSigner`.** `algorithm = "HMAC-SHA256"`, `trust_level =
   "LOCALLY_PROVEN"`. The key is the module constant
   `b"BRAINK-TEST-ONLY-KEY-NOT-A-SECRET"`, published on purpose and marked in the
   source as not a secret. `sign` returns an envelope carrying
   `payload_hash = canonical_hash(payload)`, the key id, the algorithm, the hex
   MAC and `verified = True`.
3. **`verify`.** Returns `False` — never raises — when either argument is
   `None`, when the algorithm differs, when the key id differs, or when the
   payload hash does not match. Only then does it compare MACs, using
   `hmac.compare_digest` so the comparison is constant-time. Returning `False`
   rather than raising keeps verification usable in a loop over untrusted input.
4. **`ProductionSignerPlaceholder`.** `algorithm = "ED25519-OR-KMS-BACKED"`,
   `trust_level = "DEFINED"`, `key_id = "production-key-unconfigured"`.
   `is_configured()` reports whether the named environment variable is non-empty
   — and nothing else changes if it is. `sign` and `verify` both raise
   `NotImplementedError("Production signer not configured. Provide key via
   environment.")`. Fail-closed is the entire point: a placeholder that returned a
   plausible-looking envelope would be worse than no signer at all.
5. **`__test__ = False`** is set on `TestSigner` so that pytest does not attempt
   to collect it as a test class.

## Required skill or skillset

`payload-authentication`, skillset `trust-boundary`.

## Conceptual validation method

Because the MAC covers canonical bytes, two payloads that differ in dict ordering
verify identically while any payload that differs in content fails. HMAC-SHA256
gives existential unforgeability *under the assumption that the key is secret* —
an assumption this package deliberately breaks for `TestSigner`, which is why
`TestSigner` proves the mechanism and never proves authenticity.

## Practical validation method

`tests/test_signer.py` — 16 tests: envelope shape and field lengths; verify-true
round trip; verify-false for a tampered payload, a tampered signature, a
different key and a changed algorithm; `None` handling; the non-dict guard;
determinism across reordered dicts; `to_dict` keys; canonical payload form;
`TestSigner.trust_level == "LOCALLY_PROVEN"`; `NotImplementedError` from both
production methods with the exact message; the explicit assertion that the
production trust level is `DEFINED` and **not** `PRODUCTION_VALIDATED`; and
`is_configured()` false when the environment variable is absent.

## Current validation state

* `TestSigner`: **LOCALLY_PROVEN** — mechanism demonstrated by execution.
* `ProductionSignerPlaceholder`: **DEFINED** — interface only.

## Evidence generated

`evidence/TEST_RESULTS.json`; signature envelopes appear inside the runtime
`start`/`process_command` results and in the end-to-end proof receipt built by
`tests/test_end_to_end.py`.

## Saved representations

`src/braink_runtime/signer.py`, this document, `config/signer.example.json`
(placeholder configuration with `"secret": null` in every slot),
`registry/COMPONENT_REGISTRY.json`.

## Remaining limitations or gates

* `TestSigner` uses a **published symmetric key**. It provides no
  confidentiality, no non-repudiation and no authenticity against anyone who has
  read this repository — which is everyone.
* Symmetric MACs cannot distinguish signer from verifier; asymmetric signing
  (Ed25519) is what the production interface names, and it is not implemented.
* No key rotation, no key expiry, no revocation, no certificate chain, no
  countersignature and no trusted timestamp.
* **The gate to `PRODUCTION_VALIDATED`**: real key material held in an HSM or
  KMS, an attested key custody process, an independent verifier that does not run
  in this sandbox, and published verification results. None of these exist here,
  and no amount of local testing can substitute for them.
* Never place a real key in `config/signer.example.json`, in the source, or in
  any committed file.
