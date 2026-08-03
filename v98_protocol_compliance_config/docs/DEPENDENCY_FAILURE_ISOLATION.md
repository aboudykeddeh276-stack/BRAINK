# V99 Dependency Failure Isolation

## Runtime correction

A dependency failure is not a global runtime failure. A computer does not stop being a computer because one speaker, GPU, network adapter, provider, runner, certificate, dashboard or optional service is unavailable.

The unavailable component loses only the capability it supplies unless continuing would violate a proven safety, integrity or semantic invariant.

## Canonical rule

```text
DEPENDENCY FAILURE != GLOBAL RUNTIME FAILURE
```

The runtime path is:

```text
detect -> classify criticality -> isolate failure domain -> preserve unaffected runtimes -> select degraded or alternate path -> queue deferred work -> continue core execution -> monitor recovery condition -> reintegrate when proven healthy
```

## Dependency classes

- CORE_MANDATORY: stop only the operation whose semantic validity depends on it.
- CORE_DEGRADED: continue with reduced but valid functionality.
- OPTIONAL: bypass the feature.
- EXTERNAL_GATE: continue locally while external proof remains pending.
- REPLACEABLE: select another adapter, provider or execution plane.
- DEFERRED_COMMIT: persist work and reconcile it when the dependency returns.

## Required declaration for each agent/service

Each runtime service must declare startup dependencies, runtime dependencies, optional dependencies, fallback adapters, degraded-mode contract, health policy, retry limits, circuit-breaker policy, queue/outbox policy, rollback policy and reintegration conditions.

## Hypervisor display convention

The hypervisor must display blocked domain, affected capability, impact radius, unaffected healthy domains, continuation mode, fallback path, pending evidence, re-entry condition and core semantic validity. It must not display one blocked lane as whole-system failure.

Example:

```text
CORE RUNTIME             HEALTHY
PORTABLE EXECUTION       HEALTHY
SCHEMA VALIDATION        HEALTHY
M3 HOST VALIDATION       EXTERNAL_GATE
MIRROR APPLICATION       DEFERRED_COMMIT
TASK MONITORING          CORE_DEGRADED
OVERALL SYSTEM           OPERATIONAL_DEGRADED
```

## Bounded task packet

Every newly encountered block emits a bounded task packet containing owner, blocked capability, root cause, criticality classification, research basis, logical assessment, fallback implementation, tests, receipts, recovery path, reintegration criteria and closure evidence.

## Evidence boundary

The dependency orchestrator writes a receipt, a CSV decision matrix, task packets, a ledger entry and an outbox handoff. Those receipts prove that the failure-domain decision ran. They do not prove that an external provider, M3 runner or certificate has become healthy.
