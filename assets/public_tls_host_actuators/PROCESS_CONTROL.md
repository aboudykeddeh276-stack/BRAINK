# Process Control

## Controlled lifecycle

```text
RESOLVE RESIDENT ROOTS
→ DISCOVER HOST STATE
→ RESOLVE BINDINGS
→ BUILD DEPENDENCY SNAPSHOT
→ SUBMIT DEPENDENCY GRAPH
→ PRE-MUTATION QUALIFICATION
→ PREPARE DNS-01
→ ACME ISSUANCE
→ VERIFY RETURNED MATERIAL
→ INSTALL SERVER CERTIFICATE
→ RESTART SERVER FABRIC
→ LIVE CERTIFICATE READBACK
→ EXTERNAL TRUST/HOSTNAME READBACK
→ CLEAN CHALLENGE
→ COMMIT RECEIPTS
```

Any failed consequential stage transitions to rollback or BLOCKED. Do not skip forward.

## Preconditions

Required before DNS/public certificate mutation:

- resident BRAINK/KEX root integrity accepted;
- exact repository SHA known;
- registrar database resolved unambiguously;
- server certificate/key targets resolved unambiguously;
- restart command resolved;
- ACME client available;
- DNS challenge and cleanup actuators executable;
- server install and rollback actuators executable;
- dependency graph snapshot accepted by GitHub;
- relevant tests passed on the executing host.

## DNS-01 transaction

```text
old TXT state
→ publish exact challenge
→ increment zone serial
→ read back exact TXT
→ ACME validation
→ cleanup exact challenge
→ readback challenge absent
```

Mutation outside the owning zone is forbidden.

## Certificate transaction

```text
existing cert/key snapshot
→ verify issued cert/key/chain
→ atomic install
→ restart
→ live TLS fingerprint readback
→ external hostname/trust readback
```

On any failure after install:

```text
reverse-order rollback
→ restart
→ readback restored state
→ record rollback receipt
```

## Promotion states

- `DISCOVERED` — host state observed only.
- `BOUND` — concrete host paths/interfaces resolved.
- `DEPENDENCIES_ADMITTED` — GitHub dependency submission accepted.
- `QUALIFIED` — pre-mutation tests passed.
- `CHALLENGE_PUBLISHED` — DNS-01 readback confirmed.
- `ISSUED` — public CA returned validated material.
- `SERVER_BOUND` — live service presents installed certificate.
- `PUBLIC_TLS_VERIFIED` — external hostname + system trust verification succeeded.
- `ROLLED_BACK` — mutation reversed and read back.
- `BLOCKED` — unresolved authority, dependency, ambiguity or failed invariant.

## Failure semantics

Carrier failure is reported as carrier failure. Dependency-graph failure is dependency-admission failure. Registrar failure is registrar failure. Public CA rejection is issuance failure. Do not collapse failure classes.

## Idempotency

Repeated discovery and qualification must not mutate production. DNS cleanup and rollback must be safe to retry when the targeted state is already absent/restored. Install operations must compare current and intended state before mutation where practical.

## Concurrency

Production public-TLS mutation is serialized by the deployment workflow concurrency group. Host actuators must still defend their own mutable resources because workflow serialization is orchestration, not filesystem/database locking.

## Change control

Any change to process order, status semantics, rollback conditions, required dependency cut or authority boundary requires corresponding updates to this document, schema standard, tests and workflow admission.