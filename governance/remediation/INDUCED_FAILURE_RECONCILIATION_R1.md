# BRAINK Induced Failure Reconciliation R1

## Purpose

This document records remediation for repository/process failures introduced by over-routing, stale-branch development, premature boundary classification, and governance work that did not itself reconcile existing divergence.

## Verified corrections

- GitHub availability is FULL for the connected BRAINK repository: admin/maintain/push/pull/triage are available.
- GitHub MUST NOT be classified as unavailable merely because the local container cannot resolve github.com.
- Local carrier network state and GitHub connector availability are distinct properties.
- Connector access is a valid source-sync/control path when the local carrier lacks direct network routing.

## Current induced repository divergence

### r25-governed-mcp
- state: STALE / DIVERGED
- relation to main at reconciliation start: 4 commits ahead, 16 behind
- PR #64: unmergeable
- remediation: converted back to DRAFT; no production promotion permitted

### kex/r26-process-adversarial
- state: LARGE LINEAGE FORK
- relation to main at reconciliation start: 81 commits ahead, 157 behind
- contains valid recursive-computer/R29/R30/R31 mechanics, but MUST NOT be merged wholesale
- remediation: selective conformance-based port onto a branch created from current main

## Canonical reconciliation branch

`reconcile/current-main-unification-r1`

This branch was created directly from current `main` and is the only branch authorized for current reconciliation work.

## Remediation algorithm

For every divergent implementation:

1. Resolve canonical definition/class.
2. Compare current-main implementation against divergent implementation.
3. Identify unique mechanics, not file-generation numbers.
4. Preserve explicit definitions and ontology.
5. Port only missing, proven mechanics.
6. Adapt imports/runtime contracts to current main rather than copying historical dependency trees.
7. Run current-main tests plus the mechanic's adversarial tests.
8. Reject duplicate or superseded wrappers.
9. Record source commit provenance for every ported mechanic.
10. Promote only after CI/readback on current-main lineage.

## Explicit remediation targets

### R25 governed MCP
Retain only if current main lacks equivalent:
- actor/work identity
- lease epoch validation
- scopes
- approval gating
- idempotency
- durable invocation evidence

Do NOT retain a parallel MCP server if current main already exposes a newer canonical server.

### R26-R31 recursive lineage
Evaluate separately:
- recursive constructor
- constructor admission locking
- CAS/file-lock persistence
- stale-writer reconciliation
- quarantine/recovery
- Observer² execution admission
- R30 ledger structural integrity
- R31 state-ledger recoverable logical commit

Each mechanic is promoted independently. Historical architecture/control-plane files are not promoted merely because they share the branch.

## Failure taxonomy going forward

`LOCAL_DNS_UNAVAILABLE` != `GITHUB_UNAVAILABLE`

`LOCAL_GIT_CLONE_FAILED` means only the local process path failed.

Before declaring a dependency unavailable, all already-authorized resident paths must be resolved:
- local filesystem/runtime
- connected GitHub API
- mounted Library/Drive
- resident KEX/BRAINK adapters

## Promotion block

No divergent branch may be merged wholesale until this reconciliation document is satisfied by executable tests and current-main readback.
