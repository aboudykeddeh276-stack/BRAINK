# V101.3–V101.5: IL-LLM VFS Persistence, Request Authentication, Docker Hardening

## Research basis

The public Keddeh architecture separates IL-LLM, BRAINK and KEX. IL-LLM supplies semantic and local-state context; KEX supplies addressing and lineage; BRAINK governs execution and evidence. The published construction chain is:

`word → node → node equipped with VFS → IL-LLM → bootstrapper → compiler → assembler → KEX seed → KEX engines`.

The public IL-LLM material also defines compaction as a storage contract. A digest is not a reconstruction mechanism by itself; a usable seed must identify retained material, regeneration rules and dependencies.

The KEX/Sites material further separates logical VFS capacity from physical backing and requires source-backed readback rather than treating a route or UI as proof.

## Action taken

### V101.3 — Persistence

Added `TruthBackedVFSSeedRegistry`:

- SQLite WAL + FULL synchronous mode.
- Exact source SHA-256 retained with each seed.
- Seed SHA-256 retained and verified on read.
- Regeneration contract retained.
- Dependency identities retained.
- Idempotent exact re-record is accepted.
- Same logical identity with changed source or seed is rejected.
- JSONL export retained for audit portability.

This is intentionally a registry around the existing VFS mechanics, not a second VFS implementation.

### V101.4 — Authentication / replay

Added `SignedRequestGate`:

- explicit `key_id`;
- minimum 256-bit HMAC keys;
- timestamp and bounded expiry;
- durable nonce registry;
- duplicate nonce rejection;
- signature/tamper rejection;
- key rotation by retaining multiple named keys.

The existing qualified R5 durable-execution authority is left unchanged. This is important: modifying its qualified source would invalidate the exact-source qualification receipt.

### V101.5 — Docker hardening

Added an additive `docker-compose.hardened.yml` profile rather than mutating the existing compose contract:

- non-root UID/GID;
- read-only root filesystem;
- dropped Linux capabilities;
- no-new-privileges;
- constrained `/tmp`;
- loopback-only host exposure;
- required authentication secret with no insecure default;
- CPU/memory limits;
- healthcheck;
- persistent data volume only.

## Verification

The repository test is designed to prove:

1. WAL/FULL persistence;
2. exact seed readback;
3. source tamper detection;
4. conflicting seed detection;
5. HMAC acceptance;
6. nonce replay rejection;
7. timestamp expiry rejection;
8. payload tamper rejection.

The compose verifier proves the hardened file contains the required hardening controls.

## Boundary

These changes do not establish physical multi-host durability, power-loss certification, WAN consensus, registrar control, or public deployment. Those remain separate runtime/transport claims.

They also do not turn an IL-LLM semantic digest into arbitrary data reconstruction. Reconstruction remains conditional on the retained seed, exact source identity and declared regeneration dependencies.

## Result

V101.3–V101.5 are implemented as additive, source-preserving integration surfaces around the already-qualified BRAINK/KEX mechanics. Existing qualified R5 source bytes were not rewritten.
