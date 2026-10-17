# Identity Mapping

Covers: `src/braink_runtime/canonical.py` and `src/braink_runtime/identity.py`.
**Status: UNIT_TESTED.**

These two modules are the arithmetic of the whole package. Every hash in the
ledger, every signature, every receipt hash and every component id is produced
here.

---

## Component: `canonical.py`

### Component identity
`braink:canonical` version `1.0.0`.

### Purpose
Guarantee that two logically identical objects always produce identical bytes,
and therefore identical digests, regardless of dict insertion order, Python
version or host. Without this, a hash chain is meaningless.

### Inputs
A `dict` root. `None` or a non-dict raises `ValueError`.

### Outputs
`canonical_serialize(obj) -> str`, `canonical_bytes(obj) -> bytes`,
`canonical_hash(obj) -> str` (64 lowercase hex chars),
`stable_namespace(namespace, name) -> "namespace:name"`.

### Dependencies
Stdlib `json` and `hashlib` only.

### Interfaces
```python
canonical_serialize({"b": 1, "a": 2})   # '{"a":2,"b":1}'
canonical_bytes({"a": 1})               # b'{"a":1}'
canonical_hash({"a": 1})                # 64 hex chars
stable_namespace("braink", "ledger")    # 'braink:ledger'
```

### Reconstruction rules
`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
default=str)`. Each parameter is load-bearing:
* `sort_keys=True` removes insertion-order sensitivity.
* `separators=(",", ":")` removes all insignificant whitespace.
* `ensure_ascii=True` makes the output pure ASCII, so no encoding negotiation can
  change the bytes.
* `default=str` prevents a `TypeError` on values such as `datetime`, at the cost
  of being lossy — this is an accepted, documented trade.

`canonical_bytes` is the UTF-8 encoding of that string; `canonical_hash` is
`hashlib.sha256(canonical_bytes(obj)).hexdigest()`. `stable_namespace` raises
`ValueError` if either argument is `None`.

### Required skill or skillset
`deterministic-serialization`, skillset `determinism-core`.

### Conceptual validation method
Argue from the four `json.dumps` parameters that the byte output is a function of
the object's logical content alone. Argue that digest collision resistance
reduces entirely to SHA-256's.

### Practical validation method
`tests/test_identity.py`: key-order independence, exact expected string form, the
`bytes == str.encode()` identity, 64-char digest length and the `None` guard.

### Current validation state
`UNIT_TESTED`.

### Evidence generated
`evidence/TEST_RESULTS.json`; indirectly every hash in
`evidence/LEDGER_INTEGRITY_RECEIPT.json` and `evidence/PACKAGE_MANIFEST.json`.

### Saved representations
`src/braink_runtime/canonical.py`, this document, `registry/COMPONENT_REGISTRY.json`.

### Remaining limitations or gates
Only dict roots are accepted, so lists and scalars must be wrapped by the caller.
Non-JSON-native values are coerced with `str()`, which is lossy and not
round-trippable. Floating-point values inherit Python's `repr` behaviour and are
not guaranteed stable across radically different platforms; the package avoids
floats in hashed payloads except for the rounded `confidence` value.

---

## Component: `identity.py`

### Component identity
`braink:identity` version `1.0.0`.

### Purpose
Mint stable identifiers for components, skills and services, and make it
structurally impossible for one identifier to silently denote two different
things.

### Inputs
`namespace`, `name`, `version`, `skill_name`, `service_name`, `endpoint` — all
non-empty strings; anything else raises `ValueError`. `IdentityRegistry.register`
additionally takes an `inputs` dict.

### Outputs
64-hex identity strings; registry records `{identity, inputs, fingerprint}`;
`CollisionError` on conflict; `export()` snapshot dict.

### Dependencies
`braink_runtime.canonical`.

### Interfaces
```python
generate_component_id("braink", "ledger", "1.0.0")
generate_skill_id("braink", "tamper-evident-logging")
generate_service_id("braink", "dns", "8.8.8.8:53")
detect_collision(id_a, id_b)                 # True when equal
registry = IdentityRegistry()
registry.register_component("braink", "ledger", "1.0.0")
registry.register(identity, inputs)          # raises CollisionError on conflict
registry.get(identity); registry.contains(identity)
registry.all_identities(); registry.export(); len(registry)
```

### Reconstruction rules
1. Each generator validates its arguments through a `_require` helper, then
   returns `canonical_hash` of a dict containing exactly the identifying fields:
   `{namespace, name, version}` for components, `{namespace, skill_name}` for
   skills, `{namespace, service_name, endpoint}` for services. The **field names
   are part of the hash**, so a component and a skill with the same string values
   still receive different ids.
2. `detect_collision(a, b)` returns `a == b` and raises `ValueError` on `None`.
   The naming is deliberate: equality of two independently derived ids *is* the
   collision event you want to detect.
3. `IdentityRegistry` stores `identity -> {identity, inputs, fingerprint}` where
   `fingerprint = canonical_serialize(inputs)`. Re-registering the same identity
   with the same fingerprint is idempotent and returns the existing record;
   re-registering with a different fingerprint raises `CollisionError`. This is
   the enforcement point: hash collisions are astronomically unlikely, but
   *copy-paste* collisions in a registry file are not.
4. `register_component` is sugar that derives the id and registers it with a
   `kind: "component"` input tuple that also carries
   `stable_namespace(namespace, name)`.

### Required skill or skillset
`deterministic-identity`, skillset `determinism-core`.

### Conceptual validation method
Identity is SHA-256 over a canonical tuple, so distinctness of inputs implies
distinctness of ids up to SHA-256 collision resistance, and equality of inputs
implies equality of ids unconditionally.

### Practical validation method
`tests/test_identity.py`: determinism across repeated calls, distinctness across
each varied field, blank/`None` argument rejection, skill and service id
behaviour, `detect_collision` both ways, registry registration, idempotence,
`CollisionError` on conflict, and the `export()` shape.

### Current validation state
`UNIT_TESTED`.

### Evidence generated
`evidence/TEST_RESULTS.json`; the `id` field of every entry in
`registry/COMPONENT_REGISTRY.json` and every `skill_id` in
`registry/SKILL_REGISTRY.json` was produced by these functions.

### Saved representations
`src/braink_runtime/identity.py`, this document,
`schemas/identity.schema.json`, `registry/COMPONENT_REGISTRY.json`.

### Remaining limitations or gates
The registry is in-memory only; it is not persisted, so cross-process collision
detection is not provided. There is no revocation, no rotation and no signature
over the registry itself. Identity does not imply authorisation.
