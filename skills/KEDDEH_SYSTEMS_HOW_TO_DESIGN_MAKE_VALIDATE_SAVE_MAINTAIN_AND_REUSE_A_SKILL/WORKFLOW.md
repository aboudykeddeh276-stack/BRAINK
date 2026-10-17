# Workflow

## Progressive skill-making workflow

```text
1. Preserve the literal request and intended capability.
2. Write the full semantic skill name before abbreviating anything.
3. Lock purpose, target, scope, and exclusions.
4. Identify the core mechanics that causally produce the capability.
5. Decompose all material requirements.
6. Materialise and inventory existing implementation locally when available.
7. Test existing components against their literal responsibilities.
8. Classify each component: reuse, repair/reuse, adapt/reuse, derive, reject, or unknown.
9. Define interfaces, data representation, authoritative state, and invariants.
10. Implement only missing or defective mechanics.
11. Build/import/compile.
12. Execute isolated mechanism tests.
13. Execute completed-module contract tests.
14. Execute composition/integration tests.
15. Execute relevant negative, malformed, stale, duplicate, timeout, restart, recovery, and rollback tests.
16. Execute target-specific qualification.
17. Measure performance only after correctness.
18. Qualify hardware only where the claim depends on hardware.
19. Generate and retain evidence artifacts.
20. Trace claims to requirements, mechanisms, tests, evidence, and verdicts.
21. Register passed executable capabilities as modules.
22. Save the repeatable method as a skill.
23. Package, hash, version, and persist the skill in available work environments.
24. Maintain regression, compatibility, and evidence freshness.
```

## Failure loop

```text
Execute
→ Observe
→ Compare to acceptance criterion

If PASS:
    retain evidence
    advance

If FAIL:
    classify failure
    isolate responsible mechanism
    repair smallest responsible layer
    rerun local test
    rerun dependent tests
    update evidence/status
```
