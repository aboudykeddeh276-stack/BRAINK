# Keddeh Systems — GitHub CI Failure Investigation and Root Cause Classification

**Canonical identifier:** `KEDDEH_SYSTEMS_GITHUB_CI_FAILURE_INVESTIGATION_AND_ROOT_CAUSE_CLASSIFICATION`
**Version:** 1.0.0
**Methodology reference:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

## Purpose

Fetch GitHub Actions workflow run job logs for a given run_id, parse the failure output,
classify the root cause of each failed job into a deterministic failure class from the
KEDDEH_SYSTEMS failure model, and emit a structured JSON diagnosis.

**Scope:** GitHub Actions workflow runs accessible via the GitHub REST API v3.
**Excluded:** GitLab CI, CircleCI, Jenkins, and other CI systems.

## Assumptions

- The GitHub REST API v3 is reachable.
- A valid GitHub token with `repo` read and `actions` read scope is provided.
- Log content is UTF-8 encoded text. Non-UTF-8 bytes are replaced.
- Failure classification is pattern-based (regex). Unusual failure output may classify as UNKNOWN.
- Log retrieval is via the GitHub API logs endpoint, which requires the run to have completed.

## Core mechanics

1. Fetch the run via `GET /repos/{owner}/{repo}/actions/runs/{run_id}`.
2. Fetch all jobs via `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs`.
3. Filter to jobs with `conclusion == "failure"`.
4. For each failed job, fetch the log text via
   `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs`.
5. Classify failure using the ordered pattern table in FAILURE_AND_EVIDENCE_MODEL.md.
   The first matching pattern wins.
6. Extract the most informative failure line (preferring `##[error]` annotations).
7. Emit the structured JSON diagnosis.

## Interfaces

```
Entry point:   python3 src/ci_failure_investigator.py --owner O --repo R --run-id ID [--token T]
Stdin:         not used
Stdout:        JSON diagnosis report
Stderr:        error messages
Exit codes:    0 = diagnosis produced (does not mean CI passed)
               1 = fatal error
```

## Invariants

1. Every failed job in the run appears in `failed_jobs`.
2. Each entry has: `job_id`, `job_name`, `failed_step`, `failure_line`,
   `root_cause_class`, `fix_hint`.
3. `root_cause_class` is always one of the defined classes — never null or empty.
4. If logs cannot be retrieved, `root_cause_class` is "UNKNOWN" and `failure_line` is empty.
5. The report includes `investigated_at` in ISO-8601 format and `overall_conclusion`.

## Failure classifications (defined in FAILURE_AND_EVIDENCE_MODEL.md)

`MISSING_FILE_OR_DIRECTORY`, `SYNTAX_ERROR_IN_SOURCE`, `TEST_ASSERTION_FAILED`,
`DEPENDENCY_NOT_INSTALLED`, `PERMISSION_DENIED`, `NETWORK_OR_AUTHENTICATION_ERROR`,
`TIMEOUT`, `UNKNOWN`

## Claim boundary

| Claim | Status |
|---|---|
| Failure log retrieval implemented | TRUE |
| Root cause classification implemented | TRUE |
| Network calls required at runtime | TRUE |
| All failure classes automatically fixable | FALSE — autofix is a separate skill |
