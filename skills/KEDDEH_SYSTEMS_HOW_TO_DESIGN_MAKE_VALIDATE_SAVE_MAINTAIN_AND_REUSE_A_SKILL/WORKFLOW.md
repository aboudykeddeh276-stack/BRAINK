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

 6. Materialise and inventory existing implementation locally when available.
    Output: list of found components with their file paths and responsibilities.

 7. Test each found component against its declared responsibility.
    Output: pass/fail result per component with evidence.

 8. Classify each component:
      reuse | repair-then-reuse | adapt-then-reuse | derive | reject | unknown
    Output: classification table in SKILL.md.

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

## Reuse decision tree

```
Component found?
├── No  → derive from requirements
└── Yes → test against declared responsibility
          ├── Passes → reuse
          ├── Fails, bounded defect → repair and reuse
          ├── Fails, interface mismatch → adapt and reuse
          ├── Fails, fundamentally incompatible → derive new; reject found component
          └── Cannot assess → classify as unknown; do not reuse
```

## Completion criteria

A skill package is complete when:

1. All steps produce their required outputs.
2. All required checks in the validator pass.
3. claim_boundary in manifest.json contains no false values for capabilities claimed true.
4. VERSION is set and matches manifest.json.
5. Evidence artifacts exist for all claims marked true.
