# Workflow Control

## Pull lineage

The controlled promotion chain is:

```text
asset/public-tls-host-actuators-r1
        ↓ PR #68
reconcile/current-main-unification-r1
        ↓ PR #65
main
```

Do not bypass the reconciliation branch for this asset unless a new explicit migration plan replaces this lineage.

## Required workflows

### BRAINK Dependency Graph Admission

Purpose:
- generate semantic dependency graph;
- generate GitHub dependency snapshot from exact checked-out SHA;
- submit snapshot;
- require GitHub `result=SUCCESS`;
- run dependency review after submission.

Failure means dependency admission failed, not application-runtime failure.

### Current Main Recursive Dependency Reconciliation

Purpose:
- validate dependency graph cut;
- compile integrated runtime;
- run recursive persistence, R30/R31, resident-root, TLS, DNS and actuator tests.

### Deploy BRAINK Public Services

Purpose:
- regenerate dependency graph for exact deployment SHA;
- submit dependency snapshot before mutation;
- discover/resolve host bindings;
- install launchers;
- qualify TLS/actuator code;
- deploy resident fabric;
- perform public issuance and readback transaction;
- publish receipts.

## Workflow event rules

- Pull requests qualify code and dependency changes.
- Push/workflow-dispatch may run production deployment only on a branch where production mutation is explicitly intended.
- A workflow trigger is not proof of job execution.
- `queued`/`pending` is not success.
- zero instantiated jobs is a runner/allocation boundary and must be reported as such.

## Runner rules

Where host-resident state under `/mnt/data/keddeh_deploy/...` is required, use self-hosted runner labels that actually expose that substrate. Hosted runners are not equivalent substitutes.

## Dependency Graph control

The required graph cut includes package/module/repository/runtime-authority dependencies needed by the public issuance path. Mutation must not begin until the exact deployment SHA snapshot is accepted.

## Required pull evidence

Before merging PR #68:

- changed-file scope reviewed;
- dependency graph accepted;
- actuator tests executed;
- no unresolved review threads affecting safety/authority;
- production workflow syntax/contract accepted;
- no secrets/private key material committed.

Before promoting PR #65 toward main, re-run the full reconciliation with PR #68 integrated.

## Workflow mutation accountability

Changes to:

- runner labels;
- permissions;
- dependency submission;
- production environment variables;
- concurrency;
- mutation order;
- artifact retention;
- rollback invocation;

are control-plane changes and require explicit review as such.