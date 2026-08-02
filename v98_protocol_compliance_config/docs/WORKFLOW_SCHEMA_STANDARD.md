# V98 WORKFLOW Schema Standard

## Purpose

The WORKFLOW Schema turns software work naming into a governed, testable delivery-control surface. It separates stable work identity from changing metadata so branches, commits, pull requests, tasks, deployments and dashboards can be linked without renaming churn.

The uploaded research report establishes the core rule: keep a short portable machine-safe slug for work items and branches; keep human titles readable; store mutable metadata such as status, owner, priority, environment and dates in structured fields or labels. The V98 implementation converts that rule into `config/workflow_schema.json`, `src/keddeh_workflow_schema_guard.py`, tests, receipts, ledger readback and outbox handoff.

## What it governs

The schema governs:

- native tracker references such as `KEX-98`, `PAY-142` or `owner/repo#415`
- portable slugs such as `workflow-schema-guard-service-spine`
- human titles
- workflow levels: epic, feature, story, task, subtask
- lifecycle statuses: proposed, ready, in-progress, blocked, in-review, ready-for-release, deployed, done, cancelled
- structured labels using the `wf-` prefix
- branch names in `<kind>/<ref>/<slug>` form
- conventional commit messages with required work references
- PR/MR titles with required work references
- RFC3339 timestamps and SemVer release targets

## Why it matters to V98/V99

The KEDDEH service spine now contains many executable lanes: protocol compliance, mirror lane, agent registry, runtime service, BTC Core router, mesh scheduler, target-host receipts and milestone monitor. Without a naming and roadmap schema, those lanes can be present but difficult to trace across planning, code, CI, deployment, and worker reports.

The WORKFLOW guard prevents that drift by giving every task a stable reference, every branch and PR a valid route back to the work item, and every roadmap item structured metadata that can be queried or exported.

## Execution boundary

Workflow compliance is not proof of delivery. A valid name improves traceability. It does not prove code execution, target-host operation, provider acknowledgement, ISO certification, security assurance or product correctness.

A complete work item still requires:

```text
source code
+ executable command
+ test
+ receipt write
+ ledger readback
+ outbox handoff
+ target-host/provider receipt where required
```

## Local command

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_workflow_schema_guard.py --root . --emit-receipt
python3 -m unittest tests.test_workflow_schema_guard -v
```

## Outputs

- `evidence/workflow_schema_guard_receipt.json`
- `exports/workflow_schema_guard_matrix.csv`
- `runtime_volume/proof_bundles.ledger`
- `runtime_volume/outbox/workflow_schema/*.handoff.json`

## Deployment route

The guard is wired into `scripts/run.command` and the host acceptance workflow. The current branch name predates the strict branch grammar, so the CI guard runs a controlled sample and receipt-backed policy check rather than failing PR #32 for historical branch naming. Future enforcement can be applied through repository rulesets, commit hooks, GitHub Actions and GitLab CI after transition.
