# BRAINK/KEX Estate Evolution Process

## Purpose

Apply the engineering lessons now proven useful across repositories without flattening distinct component ownership or creating duplicate abstractions.

## Canonical evolution loop

```text
DISCOVER ACTUAL MECHANIC
→ RESOLVE OWNING REPOSITORY
→ CLASSIFY COMPONENT
→ READ EXISTING GOVERNANCE/INVENTORY
→ REGISTER WORKLOAD
→ SPECIFY INTERFACE + AUTHORITY + DEPENDENCIES
→ IMPLEMENT AT OWNER
→ ADD/UPDATE CONTROL DOCUMENTS
→ DECLARE DEPENDENCY FRAGMENT
→ IMPLEMENT SMALLEST CONSUMER ADAPTER
→ DEFINE FALSIFIABLE PROOF
→ SELECT EXECUTION LANE BY CAPABILITY
→ EXECUTE
→ READ BACK
→ RECONCILE EVIDENCE
→ PATCH OWNER OF FIRST REAL DEFECT
→ UPDATE REGISTRIES/CONTROLS
→ PROMOTE ONLY TO OBSERVED EVIDENCE LEVEL
```

## No-duplication rule

Before adding a runtime, adapter or migration mechanic, search the estate for an existing class with the required responsibility. If found, evolve the owning mechanic and consume it by contract. Do not create a parallel implementation merely because the consumer repository is convenient.

## Repository responsibilities

Every consequential component should resolve:
- one canonical owner repository;
- one component/class identifier;
- source/runtime paths;
- producer and consumer interfaces;
- dependency classes;
- authority and mutation boundary;
- state/persistence boundary;
- proof conditions;
- rollback/failure handling;
- filing/evidence schema;
- cross-platform capability contract;
- active workload and promotion state.

## Development vs proof

```text
code exists
≠ code executed
≠ isolated qualification
≠ integration qualification
≠ cross-process proof
≠ cross-machine proof
≠ external interoperability
≠ repeatability
```

Claims use the L0-L12 research qualification model. Repository-local evidence conventions may be narrower; cross-repository reconciliation maps local proof into the BRAINK/KEX evidence model without rewriting the owner's records.

## Execution-lane rule

Proof requirements choose capabilities. Executors provide capabilities.

```text
PROOF REQUIREMENT
→ CAPABILITY SET
→ EXECUTOR REGISTRY
→ AVAILABLE EXECUTION LANE
```

If an executor is unavailable, classify the lane `BLOCKED/EXECUTOR_UNAVAILABLE`. Do not reject the application claim without an executed contradiction.

No single CI provider or runner class is the sole source of system truth.

## Cross-repository rule

Use `governance/control_skeleton/CROSS_REPOSITORY_COMPONENT_PROTOCOL.md`.

Owner component receipts prove owner semantics only. Consumer receipts prove consumer semantics only. Higher-level qualification composes both with exact repository revisions.

## Control-document propagation

When a mechanic materially evolves, inspect and update as applicable:
1. owning repository inventory;
2. workload register;
3. component spec;
4. control index;
5. process/workflow control;
6. filing/evidence standard;
7. authorship/authority contract;
8. dependency fragment;
9. qualification tests;
10. consumer dependency graph;
11. estate governance target registry;
12. research claim/claim registry;
13. pull-request promotion chain.

Do not mechanically generate every document for pure helpers. Apply the profile matrix and inherit controls where semantics have not changed.

## Defect routing

Classify a failure before editing:

```text
OWNER IMPLEMENTATION DEFECT
CONSUMER ADAPTER DEFECT
CONTRACT/REVISION MISMATCH
PERSISTENCE DEFECT
AUTHORITY DEFECT
CARRIER CORRUPTION
EXECUTOR UNAVAILABLE
QUALIFICATION DEFECT
EVIDENCE/SCHEMA DEFECT
```

Patch the responsible layer, then rerun the nearest falsifiable test and its downstream consumers.

## Promotion control

Promotion requires evidence, not confidence language.

Every promotion record should answer:
- What was observed?
- On which exact revisions?
- Through which executor and interface?
- What invariant passed?
- What evidence level was achieved?
- What is still unsupported?
- What rollback/recovery result exists?
- What dependent components must be requalified?

## Recursive adoption

Apply this process next to components in `GOVERNANCE_TARGET_REGISTRY.json`, prioritizing components with both existing mechanics and consequential cross-sector dependencies. An unresolved target moves to `SPECIFIED` only after its actual owner/mechanics are discovered; template generation must never invent authority or substrate semantics.
