# Resident Runtime State

`runtime/` is the resident state/control carrier for BRAINK/KEX services. It is not merely a cache directory: files here represent service bindings, architectural invariants, VFS/service-state contracts, checkpoints, idempotency/outbox state, workbook mounts and continuation records used by the resident runtime.

## Host model

The runtime is anchored to the existing Keddeh server/daemon lineage rather than GitHub workflow execution:

```text
K-Cloud / server substrate lineage
→ BRAINK resident controller
→ supervised WBOS action server
→ supervised recursive IL-LLM service
→ runtime state / readback / proof / continuation
```

GitHub may carry source and independent audit evidence. Removing GitHub workflow execution must not stop the resident service control loop.

## Architectural binding files

`KEX_RESIDENT_SERVICE_BINDING_R1.json` records the host/service relationship and separates resident operation, TL2 transport, public publication and optional external adapters.

`KEX_ARCHITECTURE_INVARIANTS_R1.json` records cross-cutting invariants such as:

- resident host ownership of liveness;
- current supervisor/generation identity;
- proof/readback separation from source/configuration;
- single idempotency ownership;
- bounded workbook semantics;
- filesystem containment;
- non-destructive evidence tests;
- TL2 generation/readback requirements;
- runtime-owned recovery/continuation.

## Virtual service state

Keddeh Systems service classes such as DNS/domain authority, HTTP, mail/messaging, registrar, server/mesh and VFS/memory should not disappear merely because an external actuator is unavailable. The runtime model separates:

```text
resident authority object
→ VFS-backed service state
→ optional physical/external actuator
```

An unavailable actuator therefore creates an external gate or pending action, not proof that the service class has no identity/state in the system.

## IL-LLM state

The recursive IL-LLM runtime maintains live topology in memory through `modules/kex_wbos/illlm_service.py`. Persistent/historical topology and cross-repository carrier descriptions are hydrated into that service. Normal updates should use graph/fact deltas where possible; full rebuild is a recovery/reindex operation.

Important distinction:

```text
primary: identity / definition / relation / lowering / proof
secondary: context / observer projection / memory / continuation
```

## Workbook state

`runtime/workbooks/` is a resident workbook mount for uploaded/activated workbook sources. Semantic sidecars describe formula/dependency structure and must be refreshed or invalidated after mutations.

## Evidence state

The runtime may maintain:

- idempotency registries;
- outbox state;
- supervisor current state/history;
- content-addressed object metadata;
- ledger checkpoints;
- capability-fabric reports;
- continuation records.

Tests must not destroy or overwrite production/resident evidence. Test evidence should use isolated paths.

## Continuation

Continuation records are executable restart state for engineering work. They should contain exact branch/PR identity, implemented mechanics, unresolved defects, promotion boundaries and restart protocol. They exist so interruption does not cause architectural rediscovery or false reset-to-baseline behavior.

## Claim boundary

A runtime file is evidence of persisted state only for the object it represents. File presence alone does not prove a process is currently executing, a tunnel is live, a public site is reachable or an external participant has completed its action.
