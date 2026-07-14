# Codex Worker Contract — KEX/BRAINK Fleet 2026-07-14

## Input packet

Each worker receives:

- one repository and one exclusive implementation lane;
- the fleet manifest;
- the KEX/BRAINK bilateral polygon baseline `0.8166666666666668`;
- the exact mathematical controls listed in the manifest;
- an issue containing acceptance tests and prohibited substitutions.

## Six-axis execution receipt

A worker must report the following six axes, each supported by explicit predicates:

1. `anchor_fidelity`
2. `factor_completeness`
3. `translation_fidelity`
4. `action_execution`
5. `validation_strength`
6. `preservation_continuity`

`polygon_average = sum(axis_scores) / 6`

A worker output is merge-eligible only when:

- `polygon_average >= 0.8166666666666668`;
- anchor, action, and preservation axes are complete;
- the assigned acceptance tests pass;
- neutral/uniform inputs do not acquire learned drift;
- no existing public contract regresses without an explicit migration.

## Bilateral readback

Before finishing, the worker must compare the delivered result to every required output in its issue:

`coverage = satisfied_required_outputs / required_outputs`

A nonzero residual must be listed as a follow-up route or blocker. It may not be hidden by prose.

## Branch and pull-request rules

- Branch prefix: `codex-fleet/WNN-<short-lane>`.
- Open a **draft PR** against the repository default branch.
- Keep changes within the assigned repository.
- Include changed files, commands executed, test output, remaining blockers, and rollback instructions.
- Do not merge.

## Prohibited substitutions

- report-only completion when executable action is available;
- synthetic/random telemetry presented as measurement;
- SHA/hash reinterpretation as KEX state identity;
- changing theorem constants solely to make tests pass;
- embedding secrets or credentials;
- external deployment, billing, DNS, TLS, or production mutation without explicit authorization;
- claiming cross-host, quantum, biological, sentient, or production proof from local tests.

## Completion artifact

Every draft PR body must include:

```text
worker_id:
route:
source_anchor:
implemented_slice:
commands:
tests:
polygon_axes:
polygon_average:
bilateral_coverage:
blockers:
rollback:
next_route:
```
