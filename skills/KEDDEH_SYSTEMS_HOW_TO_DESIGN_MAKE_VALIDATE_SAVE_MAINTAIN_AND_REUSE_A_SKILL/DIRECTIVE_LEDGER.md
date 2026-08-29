# Authoritative Naming and Semantic-Preservation Governing Correction

This directive supersedes compressed internal-code naming as the governing naming
doctrine for all Keddeh Systems skill creation and engineering artefacts.

## Governing correction

The authoritative skill identity is:

**Keddeh Systems — How to Design, Make, Validate, Save, Maintain, and Reuse a Skill**

Filesystem/package-stable identifier:

`KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

Do not use identifiers such as `SKILL-INV-01`, `F4`, `T2`, `KS-SKILL-CORE`, or
similar compressed codes as the authoritative representation of a requirement,
invariant, failure class, test layer, workflow, or skill. If concise aliases
eventually become useful, they are secondary references only; the full semantic
identity remains authoritative.

## Naming law

```
semantic accuracy
→ functional specificity
→ objective scope
→ unambiguous interpretation
→ traceability
→ concision
```

## Acceptance test

> A technically competent person unfamiliar with the project should be able to
> understand what the skill enables from its authoritative name without decoding
> project-specific shorthand.

## Semantic-preservation rule

Let `D` be a complete semantic description, `C(D)` a compressed representation,
and `R` a reconstruction process.

```
R(C(D)) = D
```

Compression is acceptable only if every material distinction necessary to understand
and execute the capability survives that transformation.

If reconstruction requires undocumented project knowledge, the representation is
lossy and must not become authoritative.

## Sub-skill naming examples

Instead of `SKILL-INV-01`, use:
```
Invariant — Preserve the Literal Purpose of the Requested Capability
machine id: PRESERVE_THE_LITERAL_PURPOSE_OF_THE_REQUESTED_CAPABILITY
```

Instead of `F4 — Protocol Violation`, use:
```
Failure Classification — Implementation Violates an Applicable Protocol
machine id: IMPLEMENTATION_VIOLATES_AN_APPLICABLE_PROTOCOL
```

Instead of `T2`, use:
```
Test Layer — Test the Completed Module Against Its Declared Contract
machine id: TEST_THE_COMPLETED_MODULE_AGAINST_ITS_DECLARED_CONTRACT
```

## This rule applies to

- Skill names
- Requirements
- State names
- Interface operations
- Failure classifications
- Evidence classifications
- Protocol messages
- Hardware dependencies
- Units
- Test identities
- Workflow stages
- Claim boundaries

## Engineering data

The semantic information contained in the name is engineering data.
Names are not cosmetic labels.

## Architecture of abstraction

```
EXPLICIT SEMANTICS FIRST
        ↓
REAL IMPLEMENTATION
        ↓
REPEATED USE
        ↓
STABLE PATTERN OBSERVED
        ↓
EQUIVALENCE DEMONSTRATED
        ↓
OPTIONAL ABSTRACTION
        ↓
OPTIONAL COMPRESSION
```

Not abstraction before understanding.
