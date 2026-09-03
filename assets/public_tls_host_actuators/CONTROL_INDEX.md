# Public TLS Host Actuator Control Index

## Purpose

This directory is a governed runtime asset. It binds BRAINK/KEX resident authority state to concrete host-side public TLS operations without redefining BRAINK, KEX, DNS, registrar, TLS, server, cloud, or carrier semantics.

Execution order is authoritative:

1. resolve resident BRAINK/KEX state;
2. resolve concrete host bindings;
3. generate executable actuator launchers;
4. generate and submit the exact dependency snapshot for the deployment SHA;
5. qualify local actuator/runtime tests;
6. publish DNS-01 challenge through resident registrar authority;
7. obtain public CA issuance through the configured ACME client;
8. verify returned key/certificate/chain material;
9. install into SERVER_ROOT;
10. restart resident fabric;
11. verify the certificate actually presented by the live server;
12. verify external hostname and system trust;
13. publish receipts or roll back.

## Governing documents

- `CONTROL_INDEX.md` — subsystem map and document precedence.
- `FILING_STANDARD.md` — file placement, names, evidence paths and retention rules.
- `SCHEMA_STANDARD.md` — machine-readable schema, versioning and compatibility rules.
- `AUTHORSHIP_AUTHORITY.md` — authorship, ownership, mutation authority and review accountability.
- `PROCESS_CONTROL.md` — lifecycle, preconditions, transitions, rollback and promotion gates.
- `WORKFLOW_CONTROL.md` — GitHub Actions, Dependency Graph and pull-chain controls.
- `OPERATIONS_RUNBOOK.md` — operator instructions, help, incident handling and administration.
- `CROSS_PLATFORM_CONTRACT.md` — portability boundaries and host capability contracts.
- `ACCOUNTABILITY_EVIDENCE.md` — receipts, proof classes, audit requirements and failure reporting.
- `KEY_CONSIDERATIONS.md` — security, reliability, interoperability and deployment constraints.

## Document precedence

When documents conflict, use this order:

1. resident BRAINK/KEX typed-root state and runtime invariants;
2. `PROCESS_CONTROL.md` and `SCHEMA_STANDARD.md`;
3. `WORKFLOW_CONTROL.md`;
4. `AUTHORSHIP_AUTHORITY.md`;
5. `FILING_STANDARD.md`;
6. runbook/help material.

No document may override observed runtime state, public certificate readback, GitHub dependency-submission evidence, or explicit rollback evidence.

## Promotion rule

A public TLS deployment may be described as `PUBLIC_TLS_VERIFIED` only when the same deployment SHA has:

- a successful BRAINK dependency snapshot submission;
- a complete required dependency graph cut;
- passing actuator/runtime qualification;
- successful DNS-01 challenge publication and cleanup;
- successful public CA issuance;
- SERVER_ROOT install confirmation;
- live certificate fingerprint correspondence;
- external hostname + system trust verification;
- complete receipts and rollback state.

Anything less must be reported by its actual stage.