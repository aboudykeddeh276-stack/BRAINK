# Keddeh Systems — How to Design, Make, Validate, Save, Maintain, and Reuse a Skill

**Canonical filesystem/package identifier:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`  
**Version:** 1.0.0  
**Class:** Governing Keddeh Systems skill-making methodology  
**Status:** Normative engineering skill specification; executable validator not implied by this document alone.

## Purpose

Define the complete Keddeh Systems method for turning an intended capability into a rigorously understood, logically structured, reproducible, executable, testable, evidence-backed, versioned, maintainable, and reusable skill package.

A saved skill must contain enough accurate information and process logic for another technically competent engineer, software agent, or future Keddeh Systems implementation to reproduce the intended capability without relying on undocumented assumptions, hidden reasoning, ambiguous shorthand, or prior conversational context.

## Governing naming principle

Names must communicate their actual technical purpose directly.

```text
semantic accuracy
→ functional specificity
→ objective scope
→ unambiguous interpretation
→ traceability
→ only then concision
```

A technically competent person unfamiliar with the project should be able to understand what a skill enables from its authoritative name without decoding project-specific shorthand.

Abbreviations, codes, shortened labels, and compressed identifiers must never replace the authoritative semantic name merely for convenience or visual compactness.

### Semantic-preservation rule

Let `D` be a complete semantic description, `C(D)` a compressed representation, and `R` a reconstruction process. Compression is acceptable only when `R(C(D)) = D` in the practical engineering sense that every material distinction required to understand, implement, test, operate, or audit the capability survives compression. If reconstruction requires guessing, undocumented project knowledge, or context that is not encoded in the skill package, compression is lossy and must not become authoritative.

## Governing information-preservation principle

The complete mechanics, requirements, assumptions, state transitions, interfaces, procedures, failure behaviour, tests, standards, evidence, limitations, and maintenance rules of a skill must first be represented explicitly.

```text
FULL MEANING
→ real implementation
→ repeated use
→ stable recurring structure discovered
→ equivalence demonstrated
→ optional abstraction
→ optional abbreviation
```

## What a Keddeh Systems skill is

A Keddeh Systems skill is a versioned, reproducible engineering method that explains and governs how a defined capability is understood, constructed, tested, integrated, operated, recovered, measured, evidenced, maintained, and truthfully promoted within a declared scope.

```text
MODULE
    executable capability

SKILL
    reproducible method used to understand, derive, build,
    validate, integrate, evidence, maintain, and reuse that capability
```

A source file containing implementation logic is not a completed module until its required execution and verification path passes. A document describing a capability is not a complete skill unless it preserves the reproducible engineering method that produces and validates that capability.

## Skill validity relationship

```text
Literal purpose
→ complete understanding of the core mechanics
→ complete requirements decomposition
→ identification of existing reusable components
→ explicit reuse, repair, adaptation, derivation, or rejection decision
→ interface and state contracts
→ logically ordered workflow
→ implementation
→ build
→ isolated testing
→ composed testing
→ negative testing
→ failure and recovery testing
→ target-specific qualification
→ performance and hardware qualification where actually applicable
→ evidence generation
→ requirement-to-evidence traceability
→ truthful claim determination
→ skill packaging
→ versioning
→ maintenance
→ reuse
```

## Core engineering invariants

### Preserve the literal purpose of the requested capability
The skill must solve the literal problem requested. It must not silently replace the requested capability with a generic scaffold, nearby abstraction, simulation, visual status representation, or easier substitute.

### Understand the core mechanics before designing the workflow
No workflow is authoritative until the underlying causal mechanics are understood sufficiently to justify its ordering. The skill must identify initial state, valid/invalid states, authoritative state, required inputs, transitions, outputs, invariants, irreversible actions, ordering constraints, relevant concurrency, and externally meaningful completion evidence.

### Every material requirement must have a complete traceable path
```text
Claim
→ Requirement
→ Mechanism
→ Implementation location
→ Test
→ Evidence
→ Verdict
```

### Evidence cannot be self-declared
A status field such as `PASS`, `executed`, or `E3` is not evidence by itself. Where applicable, validation must resolve artifact existence, identity/hash, producer, target/environment, test result, version relationship, freshness, and signature/attestation where claimed.

### Reuse must be demonstrated, not presumed
```text
existing component
→ inspect actual behaviour
→ test semantic equivalence
→ classify
```
Allowed classifications are: Reuse directly; Repair and reuse; Adapt and reuse; Derive new capability; Reject component; Unknown pending evidence.

### Unknown remains unknown
Missing evidence must never be silently converted into `PASS`, `FAIL`, `IMPOSSIBLE`, `HARDWARE LIMIT`, or `PRODUCTION READY`.

### Execution precedes promotion
```text
source
→ build/import/compile
→ execute
→ test
→ result
→ retained evidence
→ promotion
```

## Workflow engineering method

```text
1. Lock the literal purpose and scope.
2. Identify the target environment and relevant constraints.
3. Understand and document the core mechanics.
4. Decompose all material requirements.
5. Inventory existing components locally before repeatedly re-fetching them.
6. Test each existing component against the exact required responsibility.
7. Decide reuse, repair, adaptation, derivation, rejection, or unknown.
8. Define interfaces, data representation, state ownership, and invariants.
9. Implement only the missing or defective mechanics.
10. Build/import/compile the implementation.
11. Execute primitive tests.
12. Execute module-level contract tests.
13. Execute composed/integration tests.
14. Execute malformed, negative, stale, duplicate, timeout, and failure tests where applicable.
15. Execute restart, recovery, rollback, and durability tests where applicable.
16. Execute target-specific qualification.
17. Measure performance only after functional correctness.
18. Qualify hardware only where hardware is materially involved.
19. Generate retained evidence.
20. Map every material claim to evidence.
21. Register passed executable functions as modules.
22. Save the reproducible method as a skill.
23. Package, hash, version, and persist the skill.
24. Maintain regression and evidence freshness over time.
```

## Iterative failure loop

```text
Execute
→ Observe
→ Compare with acceptance criterion

PASS
→ retain evidence
→ advance

FAIL
→ classify failure
→ isolate responsible mechanism
→ repair the smallest responsible layer
→ rerun the local test
→ rerun dependent integration tests
→ update evidence and status
```

## Failure classifications

- Requirement is ambiguous, contradictory, incomplete, or impossible under the stated assumptions.
- Implementation does not correctly realise the required mechanics.
- Two otherwise valid components have incompatible interfaces or representations.
- Implementation violates an applicable protocol or externally governed contract.
- A real functional dependency required by the capability is absent.
- The current environment lacks a property required by the declared target.
- A measured performance path fails a defined requirement.
- A required security property cannot be established.
- The capability may work, but retained evidence cannot substantiate the claim.
- Evidence is insufficient to classify the condition further; status remains unknown.

## Bottleneck and hardware logic

Every material constraint must be classified as one of: Measured bottleneck; Theoretical protocol or mathematical bound; Functional dependency; Security dependency; Optimisation dependency; Environmental constraint; Unknown. A measured bottleneck requires measurements and attributable call paths. A theoretical bound requires derivation and assumptions. An environmental constraint describes the present target, not architectural impossibility.

## Interface, state, and data requirements

Where relevant, each software-producing skill must state callable operations, inputs, representations, units, preconditions, outputs, postconditions, errors, state mutation, concurrency, idempotency, versioning, byte order, integer width/signedness, overflow handling, canonical serialization, length rules, empty/null distinctions, and hashes/checksums where relevant.

Where mutable or persistent state exists, define owner, readers/writers, authoritative state, transitions, synchronization where required, generation/version, stale-state behaviour, duplicate-work behaviour, restart semantics, commit boundary, recovery semantics, and fail-closed conditions. Distributed consensus or voting must not be added where deterministic ownership is sufficient.

## Standards and protocol applicability

For each applicable standard or protocol, record identifier/version, requirement it governs, why it applies, exact claimed conformance, verification method, evidence, and excluded claims. Standards are selected because real mechanics depend on them, not because citations create an appearance of rigour.

## Test architecture

As materially applicable, define primitive/mechanism tests, module contract tests, composition tests, negative and malformed-input tests, restart/recovery tests, differential tests against an independent or authoritative oracle, real target integration tests, performance tests after correctness, and fault injection where failure-safety is claimed.

## Evidence engineering

Every retained evidence record should identify claim, requirement, module/skill version, target/environment, test name, executed command or operation, result, artifact location, artifact hash, toolchain/runtime identity, hardware identity where applicable, external response where applicable, and freshness where relevant.

## Performance and hardware qualification

Performance measurement begins only after functional correctness. A performance claim must identify metric/unit, workload, samples, warmup where needed, environment, tool, statistic/percentile, threshold, raw evidence, and what exact part of the system was measured.

Where hardware matters, record device/vendor/model, firmware, driver/interface, required capability, detection method, observed result, target workload, evidence, effect on the claim, and fallback where one exists. Do not describe an architecture as impossible merely because the current environment lacks a device.

## Module completion rule

An executable function/module becomes complete within declared scope only when implementation is complete, build/import/compile succeeds, module tests pass, and the required integration contract passes. Additional target-specific gates apply only where claimed.

## Skill naming standard

Authoritative names use ordinary descriptive technical language. Good examples include:

```text
Keddeh Systems — How to Design, Make, Validate, Save, Maintain, and Reuse a Skill
Bitcoin — Construct and Validate a Payout-Bearing Coinbase Transaction
Bitcoin — Build a Block-Bound Mining Workload from a Bitcoin Core Template
K-DRIVE — Recover the Latest Unambiguous Durable Storage Root
```

Compressed names such as `CORE-SKILL-01`, `BTC-WF-2`, `KSSM`, `INV-03`, or `F4` are not authoritative semantic names.

## Skill package structure

A robust package typically contains `SKILL.md`, `README.md`, `DIRECTIVE_LEDGER.md`, `REQUIREMENTS.md`, `WORKFLOW.md`, `FAILURE_AND_EVIDENCE_MODEL.md`, `manifest.json`, `VERSION`, and `SHA256SUMS`, with examples/vectors/scripts/tests added when materially required. File count is not a quality metric.

## Completion, maintenance, and reuse

A skill may be promoted to complete within declared scope only when mandatory requirements are mapped, required mechanics are specified, required modules exist, required tests have executed, evidence resolves, no unknown critical failure remains, claims match evidence, and package integrity is verified.

Changes to mechanics, interfaces, state semantics, protocol requirements, test oracles, evidence requirements, target dependencies, or standards require impact analysis and regression.

## Anti-patterns rejected

```text
documentation-as-implementation
manifest-as-evidence
source-presence-as-execution
generic-scaffold-as-sector-proof
status-field-as-test-result
similar-name-as-reuse-proof
hardware-as-generic-excuse
standards-list-as-conformance
framework-complexity-as-rigour
CI-success-as-production-proof
simulation-as-live-deployment
unknown-as-zero
unknown-as-impossible
abbreviation-as-authority
compression-before-understanding
```

## Final governing principle

```text
A skill is justified by the reproducibility of its mechanics,
not by the existence of its documentation.

A module is justified by executed capability,
not by the existence of its source code.

A claim is justified by evidence,
not by the confidence of the system making it.
```

```text
Purpose
→ Mechanics
→ Requirements
→ Workflow
→ Implementation
→ Execution
→ Verification
→ Evidence
→ Claim
→ Packaging
→ Maintenance
→ Reuse
```
