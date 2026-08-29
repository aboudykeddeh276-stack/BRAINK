# Keddeh Systems — GitHub CI Failure Pattern Autofix and Commit

**Canonical identifier:** `KEDDEH_SYSTEMS_GITHUB_CI_FAILURE_PATTERN_AUTOFIX_AND_COMMIT`
**Version:** 1.0.0
**Methodology reference:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

## Purpose

Read a structured JSON diagnosis produced by
`KEDDEH_SYSTEMS_GITHUB_CI_FAILURE_INVESTIGATION_AND_ROOT_CAUSE_CLASSIFICATION`,
select an applicable deterministic fix handler for each failure class, apply the fix
to repository workflow files in-place, and produce a structured JSON report of what
was changed.

**Scope:** MISSING_FILE_OR_DIRECTORY failures in GitHub Actions workflow YAML files.
**Excluded:** Source code syntax errors, test failures, network errors, and any failure
class where automated modification of non-workflow files would be unsafe.

## Assumptions

- The diagnosis JSON was produced by ci_failure_investigator.py.
- The repository root contains `.github/workflows/` with YAML workflow files.
- The failing job name in the diagnosis matches a job key in at least one workflow file.
- YAML structure is standard (indented run blocks). Unusual YAML (anchors, templates)
  may not be handled correctly — `applied` will be false with an explanatory message.
- No network access is required. This skill operates entirely on local files.

## Core mechanics

1. Parse the diagnosis JSON.
2. For each failed job:
   a. If `root_cause_class == MISSING_FILE_OR_DIRECTORY`:
      - Extract the missing path from `failure_line`.
      - Find the workflow file containing the job name.
      - Check whether `mkdir -p <path>` already exists.
      - If not, insert it into the first `run: |` block of the job.
   b. All other classes: add to `fixes_not_applicable` with reason.
3. Emit the structured report. In `--dry-run` mode, do not write any files.

## Interfaces

```
Entry point:   python3 src/ci_autofix.py --diagnosis-file FILE [--root DIR] [--dry-run]
Stdin:         not used
Stdout:        JSON report
Stderr:        error messages
Exit codes:    0 = report produced (check fixes_applied[].applied for actual results)
               1 = fatal error reading diagnosis file
```

## Invariants

1. No file is ever modified without a diagnosis entry that justifies the change.
2. In `--dry-run` mode, no filesystem writes occur; `applied` reflects what would happen.
3. If `mkdir -p <path>` already exists in the workflow, no duplicate is inserted.
4. Every failed job in the diagnosis appears in either `fixes_applied` or `fixes_not_applicable`.
5. `applied: false` entries include a human-readable `change_description` explaining why.

## Claim boundary

| Claim | Status |
|---|---|
| MISSING_FILE_OR_DIRECTORY autofix implemented | TRUE |
| Dry-run mode implemented | TRUE |
| Network calls required at runtime | FALSE — local files only |
| Source code file modification | FALSE — workflow files only |
| All failure classes automatically fixable | FALSE — MISSING_FILE_OR_DIRECTORY only |
