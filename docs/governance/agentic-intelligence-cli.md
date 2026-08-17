# BRAINK/KEX Proof-Bearing Command Runtime

## Purpose

`scripts/braink-agent-cli.py` is the repository-facing command planner for BRAINK/KEX. It treats repositories as evidence-bearing engineering sectors rather than product-state authorities.

A successful GitHub operation proves only that repository state changed. It does not prove that the system objective advanced.

## Execution law

```text
INTENT
-> VERIFY_ACTUAL_STATE
-> LOCATE_EXISTING_MECHANIC
-> RESOLVE_REAL_DEPENDENCY
-> EXECUTE_BOUNDED_ACTION
-> READ_BACK
-> CLASSIFY_EVIDENCE
-> FOLLOW_DESCENDANTS
-> DERIVE_NEXT_ROUTE
```

## Commands

```bash
./scripts/braink-agent-cli.py status
./scripts/braink-agent-cli.py scan --repo-root .. --intent "<objective>"
./scripts/braink-agent-cli.py plan --repo . --intent "<bounded objective>"
```

`scan` inventories available repositories and derives routes from observed state. `plan` emits a command packet for one repository. Neither command executes arbitrary repository code.

## Command packet contract

Every derived packet records:

- `command_id`
- `intent`
- `requirement`
- `observed_state`
- `authority`
- `invariant`
- `expected_effect`
- `test_method`
- `promotion_criterion`
- `admissible`
- `blockers`
- `next_valid_routes`

This prevents command completion from being confused with engineering completion.

## Evidence vocabulary

The runtime distinguishes:

`UNKNOWN`, `OBSERVED`, `SOURCE_VERIFIED`, `IMPLEMENTED`, `TESTED`, `VALIDATED`, `INTEGRATION_CANDIDATE`, `ACCEPTED`, `DEPLOYED`, `OPERATIONALLY_PROVEN`, `INFERRED`, `UNTESTED`, `FAILED`, `BLOCKED`, `SUPERSEDED`, `HISTORICAL`, and `RECONSTRUCTED_FROM_CURRENT_LINEAGE`.

These labels are evidence classifications, not decorative maturity names. A state may only be promoted when the required evidence exists.

## Proof output

Plans include a canonical SHA-256 digest over the emitted payload. The digest establishes deterministic identity of the plan content; it does not prove correctness of the plan's claims.

## Failure retention

A failed implementation, test, assumption, or route is evidence. It should be classified and retained rather than silently overwritten. Newer repository state must not destroy a stronger implementation merely because it is newer.

## Architecture boundary

GitHub is an engineering substrate for branches, candidates, experiments, failures, evidence, modules, releases, and integration states. GitHub location does not determine maturity.

The planner remains deliberately defensive:

- repository inspection is read-only;
- arbitrary discovered code is not executed;
- working code and lineage are preserved until evidence justifies modification;
- dirty repositories require inspection before change;
- incomplete governance is exposed as a blocker rather than silently repaired;
- remote or unavailable environments are reported as boundaries, not reinterpreted as architecture defects.

## Next engineering gates

1. Introduce an explicit allowlisted verification runner.
2. Persist append-only command/result evidence records.
3. Link each result to parent command, repository head, affected invariant, and instantiated descendants.
4. Add candidate comparison so promotion is based on test evidence rather than recency.
5. Add adapters for IL-LLM/KEX address traversal without making GitHub the architectural root.
6. Add warm-boot state rehydration from the evidence ledger.
