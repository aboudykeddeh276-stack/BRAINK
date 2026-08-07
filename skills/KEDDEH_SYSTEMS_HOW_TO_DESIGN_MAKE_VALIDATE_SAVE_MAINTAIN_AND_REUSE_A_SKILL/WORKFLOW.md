# Deterministic Skill-Making Workflow

## Step-by-step workflow

Each step produces a concrete, verifiable output before the next step begins.

```
 1. Write the full semantic skill name before abbreviating anything.
    Output: skill name that passes the acceptance test in DIRECTIVE_LEDGER.md.

 2. Lock the literal purpose, target, scope, and exclusions.
    Output: Purpose section in SKILL.md with explicit scope and non-scope.

 3. List all assumptions the skill depends on.
    Output: Assumptions section in SKILL.md.

 4. Identify the core mechanics that causally produce the capability.
    Output: Core mechanics description in SKILL.md.

 5. Decompose all material requirements.
    Output: REQUIREMENTS.md or Requirements section in SKILL.md.

 6. Materialise existing implementation locally and classify it as source material.
    Existing files are inputs to analysis, not dependencies, until validated.
    Output: inventory of found artifacts with file paths, classified as SOURCE MATERIAL.

 7. Decompose each source artifact into atomic mechanics and validate each mechanic
    independently against its required behaviour.
    Output: per-mechanic classification — valid | partial | invalid | unverified | irrelevant.

 8. Decide reuse at the smallest validated semantic unit (see REUSE_DOCTRINE.md):
      reuse-mechanic | repair-then-reuse | adapt-then-reuse | derive | reject | unknown.
    Reconstruct cleanly when the containing artifact introduces unproven assumptions,
    irrelevant state, or architectural coupling; do not import a defective module wholesale.
    Output: reuse decision table in SKILL.md keyed to individual mechanics.

 9. Define interfaces, data representation, authoritative state, and invariants.
    Output: Interfaces, State, and Invariants sections in SKILL.md.

10. Implement only missing or defective mechanics.
    Output: source files in src/.

11. Build / import / compile.
    Output: zero build errors; compilation evidence in evidence/.

12. Execute isolated mechanism tests.
    Output: all primitive tests pass; test evidence retained.

13. Execute completed-module contract tests.
    Output: all contract tests pass; evidence retained.

14. Execute composition and integration tests.
    Output: all integration tests pass; evidence retained.

15. Execute negative, malformed, stale, duplicate, timeout, restart, and recovery tests.
    Output: all negative tests pass; evidence retained.

16. Execute target-specific qualification.
    Output: qualification evidence for declared target environment.

17. Measure performance only after correctness.
    Output: performance evidence where the claim depends on measured throughput or latency.

18. Qualify hardware only where the claim depends on hardware.
    Output: hardware qualification evidence.

19. Generate and retain evidence artifacts.
    Output: evidence/ directory with artifacts keyed to claims.

20. Trace every claim to: requirement → mechanism → test → evidence → verdict.
    Output: claim boundary table in manifest.json.

21. Register passed executable capabilities as modules.
    Output: manifest.json with claim_boundary values set to booleans.

22. Save the repeatable method as a skill.
    Output: SKILL.md complete and self-contained.

23. Package, hash, version, and persist.
    Output: VERSION file, manifest.json, README.md.

24. Maintain regression, compatibility, and evidence freshness.
    Output: impact analysis record on every change.
```

## Failure loop

```
Execute
→ Observe
→ Compare to acceptance criterion

If PASS:
    retain evidence
    advance to next step

If FAIL:
    classify failure using FAILURE_AND_EVIDENCE_MODEL.md
    isolate the responsible mechanism
    repair at the smallest responsible layer
    rerun the local test
    rerun all tests that depend on the repaired component
    update evidence and status
    return to this step — do not advance until this step passes
```

## Negative-claim emission gate

A negative capability claim carries the burden of proof. See
`NEGATIVE_CLAIM_BURDEN_OF_PROOF.md`.

```
Emitting "not achieved" / "unavailable" / "unmanageable" / "impossible locally"?
→ Enumerate all materially plausible local routes.
→ For each route, record: TESTED_AND_FAILED (with evidence)
                          | RULED_OUT_WITH_EVIDENCE (with cited constraint).
→ Any route left untested and unexplained?
    Yes → status is EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN; do not emit the claim.
    No  → emit the claim scoped to the evidence; retain the route ledger.
```

## Reuse decision tree

Existing artifacts are classified as source material and decomposed into atomic
mechanics before any reuse decision. The decision is made per mechanic, at the
smallest validated semantic unit. See `REUSE_DOCTRINE.md`.

```
Artifact found?
├── No  → derive mechanics from requirements
└── Yes → classify as source material; decompose into atomic mechanics
          → for each mechanic, validate independently against required behaviour
            ├── Valid → reuse the mechanic (smallest validated unit)
            ├── Partial, bounded defect → repair at smallest layer, then reuse
            ├── Interface mismatch → adapt, then reuse
            ├── Invalid / fundamentally incompatible → derive clean; discard mechanic
            ├── Irrelevant → discard; do not carry into the clean module
            └── Unverified → classify as unknown; do not reuse

Promote a whole module only when the whole-module contract is proven correct;
otherwise reconstruct the module cleanly from validated mechanics only.
```

## Pipeline composition rule

```
NO MODULE ENTERS THE PIPELINE UNTIL THE MODULE IS COMPLETE IN ISOLATION.
NO PIPELINE STAGE MAY RELY ON AN UNVERIFIED SIDE EFFECT OF ANOTHER FILE.
AN EXISTING FILE IS NOT A DEPENDENCY MERELY BECAUSE IT ALREADY EXISTS.
REUSE MECHANICS, NOT ACCIDENTAL HISTORICAL STRUCTURE.
```

Keep source material and historical corpus outside the measurement domain of the
reconstructed pipeline so that coverage and test measurements describe the
reconstructed capability, not the accidental scope of the repository.

## Completion criteria

A skill package is complete when:

1. All steps produce their required outputs.
2. All required checks in the validator pass.
3. claim_boundary in manifest.json contains no false values for capabilities claimed true.
4. VERSION is set and matches manifest.json.
5. Evidence artifacts exist for all claims marked true.
