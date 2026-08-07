# Keddeh Systems — How to Design, Make, Validate, Save, Maintain, and Reuse a Skill

**Canonical identifier:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`
**Version:** 1.2.0
**Class:** Governing Keddeh Systems skill-making methodology
**Status:** Normative engineering skill specification with executable validator.

---

## Purpose

Define the complete Keddeh Systems method for turning an intended capability into a
rigorously understood, logically structured, reproducible, executable, testable,
evidence-backed, versioned, maintainable, and reusable skill package.

A saved skill must contain enough accurate information and process logic for another
technically competent engineer, software agent, or future Keddeh Systems implementation
to reproduce the intended capability without relying on undocumented assumptions, hidden
reasoning, ambiguous shorthand, or prior conversational context.

---

## Governing naming principle

```
semantic accuracy
→ functional specificity
→ objective scope
→ unambiguous interpretation
→ traceability
→ only then concision
```

A technically competent person unfamiliar with the project should be able to understand
what a skill enables from its authoritative name without decoding project-specific shorthand.

### Semantic-preservation rule

Let `D` = complete semantic description, `C(D)` = compressed representation, `R` = reconstruction.

Compression is acceptable only when `R(C(D)) = D`: every material distinction required to
understand, implement, test, operate, or audit the capability survives compression.

---

## What a Keddeh Systems skill is

```
MODULE
    executable capability

SKILL
    reproducible method used to understand, derive, build,
    validate, integrate, evidence, maintain, and reuse that capability
```

A source file is not a completed module until its required execution and verification path
passes. A document describing a capability is not a complete skill unless it preserves the
reproducible engineering method that produces and validates that capability.

---

## Assumptions

- The target execution environment is a POSIX-compatible shell or GitHub Actions runner
  unless the skill explicitly declares otherwise.
- GitHub REST API v3 is available for skills that interact with repository state.
- Python 3.10+ stdlib is available for executable skill implementations.
- No external package dependencies may be introduced unless justified in the skill manifest.

---

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `skill_directory` | filesystem path | yes | Root directory of the skill package to validate |
| `strict` | boolean flag | no | Fail on warnings as well as errors (default: false) |

## Outputs

| Output | Format | Description |
|---|---|---|
| `validation_report` | JSON (stdout) | Structured result with each check, verdict, and findings |
| Exit code | integer | 0 = pass, 1 = one or more checks failed |

---

## Skill validity relationship — full lifecycle

```
Literal purpose
→ complete understanding of the core mechanics
→ complete requirements decomposition
→ classification of existing components as source material (not authority)
→ per-mechanic extraction, independent validation, and smallest-unit reuse decision
→ clean canonical reconstruction from validated mechanics only
→ interface and state contracts
→ invariants
→ logically ordered workflow
→ implementation
→ build
→ isolated primitive testing
→ completed-module contract testing
→ composition and integration testing
→ negative / malformed / stale / duplicate / timeout / restart / recovery testing
→ target-specific qualification
→ performance qualification (where the claim depends on measured performance)
→ hardware qualification (where the claim depends on specific hardware)
→ evidence generation and retention
→ claim determination — what may truthfully be asserted
→ packaging
→ versioning
→ maintenance — regression, compatibility, evidence freshness
→ reuse — discovery, equivalence test, adaptation or derivation decision
```

---

## Interfaces

### validate_skill_package.py

```
Entry point:   python3 src/validate_skill_package.py <skill_directory> [--strict]
Stdin:         not used
Stdout:        JSON validation report (schema documented in the source file)
Stderr:        human-readable summary line per finding
Exit codes:    0 = all required checks passed
               1 = one or more required checks failed
```

---

## Authoritative state

| State | Meaning |
|---|---|
| `SKILL_PACKAGE_VALID` | All required checks passed |
| `SKILL_PACKAGE_INVALID` | One or more required checks failed |
| `SKILL_PACKAGE_UNKNOWN` | Validator could not complete — internal error |

Transitions:

```
(start)
→ SKILL_PACKAGE_UNKNOWN   validator invoked, check not yet complete
→ SKILL_PACKAGE_VALID     all required checks returned PASS
→ SKILL_PACKAGE_INVALID   at least one required check returned FAIL
```

---

## Invariants

1. **Literal purpose:** the validator must check what the methodology actually requires,
   not a simplified proxy.
2. **Claim integrity:** the validator must not report PASS on any check it did not execute.
3. **Completeness:** the validator must report every finding, not stop at the first failure.
4. **Determinism:** given the same skill directory content, the validator must always produce
   the same verdict.
5. **Traceability:** every reported finding must identify the file and field it evaluated.
6. **No false-positive maturity:** the validator must not infer capability presence from
   source existence alone.
7. **Existing artifacts are source material, not authority:** an existing component is
   classified as source material until its mechanics are extracted and independently
   validated. Reuse the smallest validated semantic unit; reconstruct cleanly when the
   containing artifact introduces unproven assumptions, irrelevant state, or coupling.
   See `REUSE_DOCTRINE.md`.
8. **Module completeness before composition:** no module enters the pipeline until it is
   complete in isolation, and no pipeline stage relies on an unverified side effect of
   another file.

---

## Required checks (normative — validator must implement all of these)

### Check 1 — Required files are present
`SKILL.md`, `manifest.json`, `VERSION` must exist in the skill directory.

### Check 2 — manifest.json is valid JSON
`manifest.json` must parse without error.

### Check 3 — manifest.json contains required fields
Required: `canonical_identifier`, `version`, `purpose`, `claim_boundary`.

### Check 4 — canonical_identifier is semantically stable
Must contain only `A-Z`, `0-9`, and `_`. Must not be empty.

### Check 5 — VERSION matches manifest.json version
Both must be present and equal after stripping whitespace.

### Check 6 — SKILL.md contains required section headings
Must contain `## Purpose`, `## Invariants`, and `## Assumptions`.

### Check 7 — claim_boundary is explicit
`claim_boundary` in manifest must be a JSON object with at least one key. Each key
must have a boolean value — no null, no placeholder strings.

### Check 8 — src/ directory contains at least one .py file
Executable implementation is required.

### Check 9 — tests/ directory contains at least one test file
A file matching `test_*.py` or `*_test.py` must exist under `tests/`.

---

## Failure classifications

See `FAILURE_AND_EVIDENCE_MODEL.md` for the authoritative list.

---

## Evidence

A passing run of the validator against this package's own directory produces
the baseline evidence that this methodology is self-consistent and executable.

Evidence artifact: `evidence/self_validation_report.json`

---

## Claim boundary

| Claim | Status |
|---|---|
| Skill methodology specified | TRUE |
| Executable skill validator implemented by this package | TRUE |
| Independent external attestation | FALSE — not claimed |
