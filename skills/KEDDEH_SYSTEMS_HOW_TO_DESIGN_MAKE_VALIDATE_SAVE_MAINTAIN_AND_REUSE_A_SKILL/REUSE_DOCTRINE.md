# Reuse Doctrine — Existing Artifacts Are Source Material, Not Authority

This directive refines the reuse and derivation rules of the Keddeh Systems
skill-making methodology. It governs how an already-existing repository component
is treated before any decision to depend on it.

The core mechanics of the skill-making lifecycle are unchanged. This document
sharpens one stage of that lifecycle: the treatment of existing artifacts.

## Governing correction

The earlier reuse rule — *"preserve a valid existing component"* — was still too
coarse. The corrected rule is:

> Treat every existing artifact first as source data. Extract its mechanics.
> Validate those mechanics independently. Reuse the smallest validated semantic
> unit that preserves the required behaviour. Reconstruct cleanly when the
> containing artifact introduces unproven assumptions, irrelevant state, or
> architectural coupling.

## Correct engineering order

```text
RAW DATA / EXISTING FILE / EXISTING CODE
        ↓
READ IT AS INFORMATION
        ↓
ANALYSE WHAT IT ACTUALLY DOES
        ↓
SCOPE THE MECHANICS IT CONTAINS
        ↓
SEPARATE VALID / PARTIAL / INVALID / IRRELEVANT LOGIC
        ↓
EXTRACT THE REUSABLE WRITTEN PROCESS
        ↓
REPRODUCE THAT PROCESS CLEANLY AS AN ISOLATED MODULE
        ↓
TEST THE NEW MODULE AGAINST ITS REQUIRED MECHANICS
        ↓
ONLY THEN COMPOSE IT INTO THE PIPELINE
```

This replaces the reversed order that connects first and validates afterward:

```text
file exists
→ import it
→ connect it
→ inherit its assumptions
→ discover later that its state model or tests were wrong
```

## Existing code is evidence, not authority

An existing repository component is initially classified as:

```text
SOURCE MATERIAL
```

It is **not** automatically classified as any of:

```text
DEPENDENCY
MODULE
IMPLEMENTATION
AUTHORITATIVE RUNTIME
```

A source file is structured data until its mechanics are evaluated. The useful
asset inside an old implementation is often not the code object itself but the
encoded reasoning it demonstrates:

```text
input
→ transformation
→ validation
→ next state
→ output
```

That process can be reconstructed independently from the protocol requirement,
the validated mathematics, and the tested process — not from an assumption that
the old file deserves architectural authority.

## The unit of reuse is the mechanic

Reuse the smallest validated semantic unit. Promote a larger unit only when the
whole unit's contract is proven correct.

```text
1. Mathematical law / protocol rule
2. Algorithm
3. Data transformation
4. Interface contract
5. Tested implementation fragment
6. Complete module
7. Complete service
```

Each level earns promotion independently. A complete module is reused whole only
when the whole-module contract is correct. Otherwise: extract the valid
mechanics, reproduce them cleanly, and discard the inherited defects.

## Per-mechanic validation classes

When decomposing an artifact into atomic mechanics, each mechanic is classified
independently before any module-level reuse decision is made:

```text
VALID
PARTIAL
INVALID
UNVERIFIED
IRRELEVANT
```

The clean canonical module contains only `VALID` mechanics. `PARTIAL` mechanics
are repaired at the smallest responsible layer before promotion. `INVALID`,
`UNVERIFIED`, and `IRRELEVANT` mechanics are not carried into the clean module.

## Governing rules

```text
AN EXISTING FILE IS NOT A DEPENDENCY MERELY BECAUSE IT ALREADY EXISTS.
```

```text
REUSE MECHANICS, NOT ACCIDENTAL HISTORICAL STRUCTURE.
```

```text
NO MODULE ENTERS THE PIPELINE UNTIL THE MODULE IS COMPLETE IN ISOLATION.
```

```text
NO PIPELINE STAGE MAY RELY ON AN UNVERIFIED SIDE EFFECT OF ANOTHER FILE.
```

## Measurement-domain separation

Keep source material and historical corpus outside the measurement domain of the
corrected, canonically reconstructed pipeline. When legacy files remain inside
the same coverage or test domain, reported measurements describe the accidental
scope of the repository rather than the reconstructed capability.

```text
reference_sources/   — inputs to analysis, not runtime dependencies
legacy/              — historical corpus, not authoritative runtime
evidence_sources/    — prior receipts and logs used as evidence only
```

A clean measurement such as `coverage(reconstructed_pipeline)` then means what
it states, because only completed modules are inside the domain.

## Relationship to the lifecycle

This doctrine governs the following lifecycle stages defined in `SKILL.md` and
`WORKFLOW.md`:

- identification of existing components as source material;
- per-mechanic extraction, classification, and independent validation;
- clean canonical reconstruction from validated mechanics only;
- isolated module completion before composition;
- composition only across validated module boundaries.
