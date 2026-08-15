# BRAINK Execution Volume Evolution V1

## Governing status

`ENGINEERING_CANDIDATE`

This document extends the existing BRAINK6/KEX runtime rather than replacing prior implementations. Existing runtime v2 remains the current canonical service/hardware spine; earlier implementations remain lineage/evidence.

## Core invariant

`NAME != SPECIFICATION != CAPABILITY != EXECUTABLE_STATE != EXTERNAL_RECEIPT`

No projection, repository, manifest, telemetry field, model response or UI status may silently promote one class into another.

## Architecture objective

Evolve BRAINK from an AI tool with callable surfaces into a canonical executable volume in which the durable unit is the continuation and every tool/API/UI/repository is an adapter or projection.

```text
HUMAN INTENT
  -> TASK
  -> CANONICAL OBJECT
  -> CAPABILITY DISCOVERY
  -> DEPENDENCY / AUTHORITY RESOLUTION
  -> ROUTE
  -> EXECUTION
  -> OBSERVATION
  -> VERIFICATION
  -> EVIDENCE
  -> STATE COMMIT
  -> CONTINUATION
  -> PROJECTION
```

## Stable plan IDs

### EV-01 — Canonical object model
Define typed identities for Requirement, Capability, Specification, Dependency, Module, Environment, Resource, Authority, State, Evidence, Failure, Projection, Adapter, Carrier, Task and Decision.

Depends: current runtime contracts.
Must be true before promotion: no consequential runtime state depends solely on display labels or untyped status strings.

### EV-02 — Continuation kernel
`tools/kex-runtime/continuation.mjs` is the first implementation of the canonical continuation primitive.

It carries task, goal, observer, logical time, working memory, registers, route stack, return stack, proof cursor, authority, evidence, obligations, failure context and projection reference.

Depends: EV-01.
Must be true: snapshot -> rehydrate preserves state root and continuation fields.

### EV-03 — Capability resolver
`tools/kex-runtime/capability-resolver.mjs` enforces discovery before derivation and returns `REUSE | ADAPT | BRIDGE | DERIVE | UNKNOWN` resolution semantics.

Depends: EV-01, EV-02, authoritative capability registry.
Must be true: a capability present in the authoritative topology cannot become unavailable merely because the current branch does not mention it.

### EV-04 — Runtime integration
`tools/kex-runtime/runtime.mjs` owns continuation lifecycle and capability resolution while preserving the existing service/hardware/rehydration runtime.

Depends: EV-02, EV-03.
Must be true: existing runtime self-test remains executable and continuation routes are ledger-visible.

### EV-05 — Evidence-bound execution
Every consequential transition receives an evidence class and receipt requirement. Internal execution evidence cannot promote itself to external authority evidence.

Depends: EV-04.
Must be true: the runtime can distinguish locally executed, tested, externally observed and externally authoritative states.

### EV-06 — Negative knowledge
Failures become typed, replayable constraints with cause, context, affected invariant, evidence, correction, regression test and prevention policy.

Depends: EV-05.
Must be true: a known failed route can influence subsequent resolution without deleting the failed lineage.

### EV-07 — Self-conformance
Replace exact demonstration-only conformance with parameterised and property-based tests over the canonical contracts.

Depends: EV-01 through EV-06.
Must be true: self-conformance can test the runtime's own invariants without treating the test runner's assertions as external proof.

### EV-08 — Recursive volume traversal
Make IL-LLM address traversal, nested volumes, route continuity and warm boot first-class runtime operations.

Depends: EV-02, EV-07.
Must be true: traversal changes logical location without creating a new cold AI session.

### EV-09 — Adapter neutrality
Expose the same canonical capability through tool, SKILL, Python, coding workspace, HTML, native and headless projections without duplicating authoritative state.

Depends: EV-03, EV-08.
Must be true: projection identity cannot become machine identity.

### EV-10 — Human service fabric
Resolve user-facing work through FIND, UNDERSTAND, DO, CHECK, RECOVER and CONTINUE services, each resolving to canonical machine capabilities.

Depends: EV-08, EV-09.
Must be true: human task language is not required to encode internal implementation topology.

### EV-11 — Cross-domain conformance
Use BTC, BOS, DNS, mesh, storage and server capabilities as distinct evidence domains connected by typed routes rather than merged into a single claim space.

Depends: EV-05, EV-06, EV-09.
Must be true: evidence does not cross runtime/authority boundaries without a declared bridge and receipt.

### EV-12 — Convergence engine
Compare candidate implementations using requirement coverage, invariants, tests, evidence, dependencies, runtime behaviour, failure profile and integration cost. Preserve rejected/superseded candidates as lineage.

Depends: EV-06, EV-07.
Must be true: convergence is evidence-based and non-destructive.

## Non-bypass law

Discovery may extend a plan item, but cannot silently replace it. A new implementation must declare which stable plan ID it satisfies and list its dependencies. An unresolved dependency is a state requiring resolution, not a terminal architectural stop.

## Completion model

A plan item is complete only when its implementation, test method, observed result, evidence classification and integration decision are recorded. `NOT_YET_PROVEN` is not equivalent to `FAILED`, and neither is equivalent to `COMPLETE`.

## Current implementation slice

This branch implements EV-02, EV-03 and EV-04 as an additive evolution from KEX Runtime v2. It deliberately does not claim EV-05 through EV-12 complete.

## Evidence boundary

The runtime model can establish software-local properties when its tests execute successfully. It cannot by itself establish public WAN, registrar, authoritative DNS, TLS, physical hardware, provider or external-network outcomes. Those require their own boundary-specific observations and receipts.
