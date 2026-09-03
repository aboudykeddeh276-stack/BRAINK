# Accountability and Evidence

## Evidence classes

Every consequential operation must emit evidence appropriate to its layer:

- dependency admission receipt;
- host discovery/binding record;
- DNS-01 mutation/cleanup receipt;
- public CA issuance receipt;
- SERVER_ROOT install receipt;
- rollback receipt where invoked;
- live TLS fingerprint readback;
- external hostname/system-trust readback;
- workflow run/job identity.

## Required accountability fields

At minimum record:

```text
repository
commit_sha
operation
actor/process/workflow identity
authority
input state or digest
mutation target
post-state/readback
proof class
status
rollback status
```

## Proof hierarchy

```text
SOURCE PRESENCE
< UNIT TEST
< LOCAL INTERFACE READBACK
< RESIDENT HOST READBACK
< EXTERNAL PROTOCOL READBACK
< EXTERNAL AUTHORITY/TRUST VERIFICATION
```

A weaker class may not be reported as a stronger one.

## Failure accountability

Failures must retain their actual class: runner allocation, dependency admission, binding ambiguity, DNS authority, ACME issuance, certificate install, TLS consumption, external trust, or rollback.

## Review accountability

PR review must examine authority and failure semantics, not only syntax. Changes that weaken proof or rollback require explicit justification.

## Evidence retention

Consequential receipts are retained under the configured evidence root and, when appropriate, uploaded as workflow artifacts. Private keys are never evidence artifacts.

## Reconciliation

If two receipts disagree, the latest observed runtime readback does not automatically erase earlier history. Record the contradiction, identify the authority class, reconcile it, then create a new receipt describing the resolution.