# BRAINK/KEX Research & Qualification Fabric

## Purpose

This package turns architectural claims into falsifiable, executable, evidence-backed engineering programmes.

The qualification fabric separates three concerns that MUST NOT be conflated:

1. **Proof definition** — what must be shown for a claim to be supported.
2. **Execution adapter** — where/how a proof is exercised.
3. **Evidence contract** — what observable result constitutes acceptable proof.

A GitHub Actions run, local pytest invocation, resident host process, remote machine, container, protocol observer or benchmark harness is an execution carrier. None of those carriers is itself the proof definition.

## Core law

```text
CONFIDENCE = f(observed evidence)
```

Never:

```text
assert confidence -> search for supporting evidence
```

## Claim lifecycle

```text
PROPOSED
-> CLASSIFIED
-> FORMALISED
-> IMPLEMENTED
-> EXECUTED
-> OBSERVED
-> REPRODUCED
-> COMPARATIVELY_EVALUATED
-> SUPPORTED | PARTIALLY_SUPPORTED | REJECTED | BLOCKED
```

## Evidence levels

- L0 concept stated
- L1 formal definition/invariants
- L2 implementation exists
- L3 implementation executes
- L4 isolated qualification passes
- L5 integration qualification passes
- L6 adversarial/failure qualification passes
- L7 restart/persistence qualification passes
- L8 cross-process qualification passes
- L9 cross-machine qualification passes
- L10 external interoperability qualification passes
- L11 repeatability established
- L12 comparative benchmark established

A claim may only be reported at the highest evidence level actually satisfied by receipts.

## Component truth model

```text
COMPONENT TRUTH
= IDENTITY
+ STATE
+ INTERFACE
+ DEPENDENCIES
+ AUTHORITY
+ PERSISTENCE
+ PROOF
```

## Qualification flow

```text
CLAIM
-> primitive reduction
-> known-CS adjacency
-> falsifiable hypothesis
-> proof requirements
-> executor selection
-> execution
-> evidence receipts
-> reconciliation
-> conclusion
-> architecture update
-> next experiment
```

## Failure classification

Execution-carrier failure is recorded as `EXECUTOR_UNAVAILABLE` and MUST NOT be reclassified as an application, runtime, protocol or architecture failure unless evidence from that layer exists.

## Promotion rule

```text
PROMOTION = REQUIRED_PROOFS_SATISFIED
```

not:

```text
PROMOTION = PREFERRED_CI_WORKFLOW_COMPLETED
```
