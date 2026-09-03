# Schema Standard

## Principle

Every consequential public-TLS object must be typed and versioned. A filename is not a schema.

## Required envelope

Machine-readable records must expose at least:

```json
{
  "schema": "kex.braink.<class>.v1",
  "record_id": "stable-or-unique-id",
  "created_ns": 0,
  "repository": "aboudykeddeh276-stack/BRAINK",
  "commit_sha": "40-hex-sha",
  "operation": "operation-name",
  "status": "PREPARED|APPLIED|VERIFIED|ROLLED_BACK|BLOCKED|FAILED",
  "authority": "authority-identifier",
  "inputs": {},
  "outputs": {},
  "proof": {},
  "rollback": {}
}
```

Fields may be extended but core meaning must not be silently changed within the same schema version.

## Canonical schema classes

- `kex.braink.host-actuator-discovery.v1`
- `kex.braink.host-actuator-bindings.v1`
- `kex.braink.dns01-actuator-receipt.v1`
- `kex.braink.server-tls-install-receipt.v1`
- `kex.braink.server-tls-rollback-receipt.v1`
- `kex.braink.public-ca-receipt.v1`
- `kex.braink.public-tls-deployment-receipt.v1`
- `kex.braink.dependency-edges.v1`

## Compatibility

A change is backward-compatible when an existing consumer can interpret the record without changing existing field meaning. Additive optional fields are generally compatible.

A new schema major/version is required when:

- required fields change;
- status semantics change;
- authority meaning changes;
- a field changes type or interpretation;
- hash/signature input canonicalization changes;
- rollback or proof semantics change.

## Canonicalization

Where records are hashed or signed:

- use UTF-8;
- sort object keys deterministically;
- use compact JSON separators;
- exclude volatile display-only fields only when the schema explicitly says so;
- record the digest algorithm.

## Binding schema requirements

Host bindings must include:

- registrar database absolute path;
- server certificate target absolute path;
- server private-key target absolute path;
- restart command absolute path;
- TLS readback host;
- TLS readback port;
- discovery source digest or identity;
- ambiguity resolution method;
- status.

## Mutation receipt requirements

DNS and SERVER_ROOT mutations must record pre-state and post-state sufficient to verify or reverse the mutation.

## Secret exclusion

Schemas may reference private-key paths and public-key fingerprints, but must not serialize private key bytes into receipts, logs, GitHub artifacts, Dependency Graph metadata or repository documents.