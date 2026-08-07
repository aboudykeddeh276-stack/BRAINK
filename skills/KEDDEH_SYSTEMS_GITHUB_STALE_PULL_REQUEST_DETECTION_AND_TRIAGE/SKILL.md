# Keddeh Systems — GitHub Stale Pull Request Detection and Triage

**Canonical identifier:** `KEDDEH_SYSTEMS_GITHUB_STALE_PULL_REQUEST_DETECTION_AND_TRIAGE`
**Version:** 1.0.0
**Methodology reference:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

## Purpose

Identify draft pull requests in a GitHub repository that have had no activity for longer
than a configurable staleness threshold, classify them as stale, and emit a structured
JSON report. Optionally post a human-readable triage comment to each stale PR via the
GitHub Issues API.

**Scope:** Draft pull requests in GitHub repositories.
**Excluded:** Non-draft PRs (staleness classification is for draft work only).

## Assumptions

- A PR's "last activity" is its `updated_at` timestamp from the GitHub API.
- "Stale" means `days_since_update >= stale_threshold_days`.
- The staleness threshold is configurable (default: 14 days).
- Comment posting requires a token with `issues: write` permission.
- Read-only operation (without `--comment`) requires only `repo: read`.

## Core mechanics

1. List all open PRs (paginated).
2. Filter to draft PRs only.
3. Compute `days_since_update = now - updated_at` in whole days.
4. Classify as stale if `days_since_update >= stale_threshold_days`.
5. Optionally post a triage comment using `POST /repos/{owner}/{repo}/issues/{number}/comments`.
6. Emit the structured JSON report.

## Interfaces

```
Entry point:   python3 src/stale_pr_janitor.py --owner O --repo R [--stale-days N] [--comment] [--token T]
Stdin:         not used
Stdout:        JSON report
Stderr:        warnings and error messages
Exit codes:    0 = report produced
               1 = fatal error
```

## Invariants

1. Only draft PRs are classified as stale. Non-draft PRs do not appear in `stale_prs`.
2. `days_stale >= stale_threshold_days` for every entry in `stale_prs`.
3. `comment_posted` is `false` if `--comment` was not passed.
4. A failed comment post is reported as a warning on stderr; the PR still appears in the report.
5. The report includes `scan_timestamp`, `stale_threshold_days`, and `repository`.

## Claim boundary

| Claim | Status |
|---|---|
| Stale draft detection implemented | TRUE |
| Comment posting implemented | TRUE |
| Non-draft PR staleness detection | FALSE — out of scope by design |
| Automatic PR closing | FALSE — not implemented; human decision required |
