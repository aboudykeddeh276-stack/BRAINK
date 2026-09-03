# BRAINK/KEX Computer Science Case Study Standard

Every consequential architectural proposition MUST be examined as both an engineering implementation and a falsifiable research claim.

## Required structure

### 1. Claim recovery
- exact named concept/class
- exact statement being evaluated
- implementation paths
- current evidence level
- prohibited interpretations

### 2. Computer-science classification
Resolve:
- state model
- execution model
- address model
- interface model
- communication model
- persistence model
- authority model
- failure model
- virtualization class

### 3. Established-CS adjacency
Identify relevant established areas without collapsing the BRAINK/KEX claim into them. Record:
- known primitive or pattern
- similarity
- difference
- proposed extension
- measurable consequence

### 4. Primitive reduction
Express the claim in components, interfaces and invariants. Avoid metaphor as proof.

### 5. Falsifiable hypothesis
Define:
- experiment
- controlled variables
- changed variables
- pass condition
- fail condition
- invalid inference

### 6. Baseline
Where a performance, complexity or capability advantage is claimed, select an established or conventional baseline and justify the comparison boundary.

### 7. Instrumentation
Record observable measures appropriate to the claim, including where relevant:
- wall-clock latency
- CPU time/cycles
- allocations/copies
- bytes transferred
- serialization/deserialization count
- syscalls
- process transitions
- state digests
- persistence/restart results
- routing/address translations
- error/failure surfaces
- recovery duration

### 8. Qualification matrix
Exercise, where applicable:
- isolated behaviour
- integration
- concurrency
- multi-process
- restart/rehydration
- destructive/failure injection
- cross-machine
- external protocol/interoperability
- repeatability
- comparative benchmark

### 9. Evidence
Every conclusion must identify receipts/artifacts and the highest achieved evidence level L0-L12.

### 10. Critique
Explicitly record:
- defects found
- confounding variables
- unsupported assumptions
- alternative explanations
- evidence gaps
- invalid overclaims

### 11. Engineering response
The case study must terminate in one or more of:
- patch
- new test
- new instrumentation
- architecture correction
- rejected claim
- narrowed claim
- next experiment

### 12. Conclusion form
Use only:

```text
OBSERVED
...

MEASURED
...

SUPPORTS
claim X to evidence level Ln

DOES NOT YET SUPPORT
...

DEFECTS / LIMITATIONS
...

ENGINEERING ACTION
...

NEXT EXPERIMENT
...
```

## Confidence rule

Confidence language is prohibited unless tied to observed evidence and a declared evidence level.

```text
confidence must be an output of evidence reconciliation
```
