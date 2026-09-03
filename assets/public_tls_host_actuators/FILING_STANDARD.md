# Filing Standard

## Scope

Applies to all source, configuration, schema, evidence, receipts, discovery outputs, bindings and operational records for the public TLS host actuator asset.

## Repository layout

```text
assets/public_tls_host_actuators/
  CONTROL_INDEX.md
  FILING_STANDARD.md
  SCHEMA_STANDARD.md
  AUTHORSHIP_AUTHORITY.md
  PROCESS_CONTROL.md
  WORKFLOW_CONTROL.md
  OPERATIONS_RUNBOOK.md
  CROSS_PLATFORM_CONTRACT.md
  ACCOUNTABILITY_EVIDENCE.md
  KEY_CONSIDERATIONS.md
  dns01_resident_actuator.py
  server_tls_actuator.py
  rollback_server_tls.py
  resolve_host_bindings.py
  install_launchers.py

tests/integration/
  test_public_tls_host_actuators.py

deploy/braink-public/
  discover_host_actuators.py
  provision_public_tls.py
  deploy_live.py
```

## Naming rules

- Python modules: lower snake case.
- Control documents: UPPER_SNAKE_CASE `.md`.
- Machine-readable schemas/receipts: lower kebab or snake case with explicit schema identifier inside the payload.
- No ambiguous names such as `final`, `new`, `fixed`, `latest`, `temp2`.
- Version semantic contracts by schema identifier, not filename churn.

## Runtime evidence root

Default resident evidence root:

```text
/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE/
```

Expected subspaces:

```text
TLS_ROOT/
PUBLIC_CA/
TLS_ACTUATORS/
HOST_ACTUATORS/
```

## Evidence filename contract

Every evidence file must identify at least:

- schema;
- UTC or epoch timestamp;
- repository;
- commit SHA;
- operation;
- actor/process identity where available;
- source state/input hash where applicable;
- result/status;
- readback/proof;
- rollback result where applicable.

Recommended shape:

```text
<CLASS>_<OPERATION>_<UTCSTAMP>_<SHORTSHA>.json
```

## Source/evidence separation

Source repository contains code, declarations and tests. Runtime evidence root contains host observations, certificates metadata, bindings, mutation receipts and rollback receipts. Private keys and live certificate secrets must never be committed to Git.

## Retention

Do not overwrite consequential receipts. Append or create new evidence records. Discovery/binding snapshots may be superseded but the exact snapshot used for a deployment must be retained with that deployment receipt.

## Filing invalidation

A file is non-authoritative when:

- it lacks schema/version identity;
- its commit SHA does not match the executing deployment;
- it is generated after the mutation it claims to authorize;
- it contradicts runtime readback;
- it contains secret material that belongs in runtime storage;
- ownership cannot be resolved.