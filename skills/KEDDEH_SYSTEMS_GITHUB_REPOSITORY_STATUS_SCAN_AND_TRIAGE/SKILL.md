# Keddeh Systems — GitHub Repository Status Scan and Triage

**Canonical identifier:** `KEDDEH_SYSTEMS_GITHUB_REPOSITORY_STATUS_SCAN_AND_TRIAGE`
**Version:** 1.0.0
**Methodology reference:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

## Purpose

Query all open pull requests in a GitHub repository, fetch the latest CI workflow run
conclusion per branch, and produce a structured JSON triage report that categorises
each PR as: ready for review, draft, stale draft, CI-failing, or merge-ready.

**Scope:** GitHub repositories accessible via the GitHub REST API v3.
**Excluded:** GitLab, Bitbucket, and any non-GitHub VCS hosting.

## Assumptions

- The GitHub REST API v3 is reachable from the execution environment.
- A valid GitHub personal access token with `repo` read scope is provided.
- Python 3.10+ stdlib is available.
- No external packages are required beyond the stdlib.
- A PR's CI status is determined by the most recent *completed* workflow run on its branch.
  If no completed run exists, status is "pending" or "unknown".

## Core mechanics

1. List all open PRs via `GET /repos/{owner}/{repo}/pulls?state=open` (paginated).
2. For each PR branch, query `GET /repos/{owner}/{repo}/actions/runs?branch={branch}`
   to find the most recent completed workflow run and read its conclusion.
3. Classify each PR:
   - Non-draft → `ready_for_review`
   - Draft, updated within threshold → `draft`
   - Draft, not updated within threshold → `stale_draft`
   - CI conclusion == "failure" → also in `ci_failing`
   - Non-draft AND CI == "success" → also in `merge_ready`
4. Emit the full triage report as JSON to stdout.

## Interfaces

```
Entry point:   python3 src/repo_status_scan.py --owner OWNER --repo REPO [--stale-days N] [--token TOKEN]
Stdin:         not used
Stdout:        JSON triage report
Stderr:        error messages
Exit codes:    0 = report produced
               1 = fatal error (auth, network, missing args)
```

## Invariants

1. Every open PR in the repository appears in at least one category in the report.
2. A non-draft PR with CI success appears in `merge_ready`.
3. A PR with CI failure appears in `ci_failing` regardless of draft state.
4. The report includes a `scan_timestamp` in ISO-8601 format.
5. PR entries include `number`, `title`, `branch`, `is_draft`, `ci_conclusion`,
   `days_since_update`, and `html_url`.
6. If the CI status cannot be determined, it is reported as "unknown", not omitted.

## Failure classifications

- `NETWORK_OR_AUTHENTICATION_ERROR` — API unreachable or token invalid.
- `MISSING_FILE_OR_DIRECTORY` — not applicable to this skill.
- `UNKNOWN` — unexpected API response shape.

## Claim boundary

| Claim | Status |
|---|---|
| Repository status scan implemented | TRUE |
| CI status per branch checked | TRUE |
| Network calls required at runtime | TRUE (GitHub API) |
| Works without a GitHub token | FALSE — token required |
