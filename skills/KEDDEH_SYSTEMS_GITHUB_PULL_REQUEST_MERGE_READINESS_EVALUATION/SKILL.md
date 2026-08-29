# Keddeh Systems — GitHub Pull Request Merge Readiness Evaluation

**Canonical identifier:** `KEDDEH_SYSTEMS_GITHUB_PULL_REQUEST_MERGE_READINESS_EVALUATION`
**Version:** 1.0.0
**Methodology reference:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

## Purpose

Evaluate a single GitHub pull request against deterministic merge-readiness criteria
and emit a structured JSON verdict with explicit blocking reasons.

**Criteria (all must be satisfied for MERGE_READY):**
1. PR is not a draft.
2. Most recent completed CI workflow run on the PR branch concluded with "success".
3. PR has no merge conflicts (`mergeable_state` is "clean", "has_hooks", or "unstable").
4. PR has no outstanding review requests.

**Scope:** Pull requests in GitHub repositories accessible via GitHub REST API v3.
**Excluded:** GitLab MRs, Bitbucket PRs, merge-queue management.

## Assumptions

- A valid GitHub token with `repo` read and `pull_requests` read scope is provided.
- CI status is assessed via the most recent *completed* workflow run on the branch.
  "pending" and "unknown" are treated as blocking.
- `mergeable_state == null` from the API (GitHub has not yet computed it) is not treated
  as a conflict — the check passes with a null state.
- Outstanding review requests are determined by `requested_reviewers` and
  `requested_teams` in the PR response.

## Interfaces

```
Entry point:   python3 src/pr_merge_readiness.py --owner O --repo R --pr N [--token T]
Stdin:         not used
Stdout:        JSON verdict
Stderr:        error messages
Exit codes:    0 = MERGE_READY
               2 = BLOCKED (one or more criteria not met)
               1 = fatal error
```

## Invariants

1. The verdict is always one of: MERGE_READY, BLOCKED_BY_DRAFT, BLOCKED_BY_CI,
   BLOCKED_BY_CONFLICT, BLOCKED_BY_REVIEW, UNKNOWN.
2. `blocking_reasons` is an empty list if and only if `verdict == MERGE_READY`.
3. `checks` always contains: `is_draft`, `ci_conclusion`, `mergeable_state`,
   `has_review_requests`.
4. If CI status cannot be determined, `ci_conclusion == "unknown"` and the verdict
   is BLOCKED_BY_CI — not MERGE_READY.
5. The report includes `evaluated_at` in ISO-8601 format.

## Claim boundary

| Claim | Status |
|---|---|
| Merge readiness evaluation implemented | TRUE |
| Blocking reason list emitted | TRUE |
| Network calls required at runtime | TRUE |
| Auto-merge action | FALSE — verdict only, no merge action |
| Required status check list configurable | FALSE — all completed CI runs assessed |
