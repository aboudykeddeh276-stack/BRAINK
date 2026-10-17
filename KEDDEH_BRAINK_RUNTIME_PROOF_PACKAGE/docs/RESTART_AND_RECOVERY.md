# Restart and Recovery

Covers: `src/braink_runtime/restart.py`.
**Status: RESTART_TESTED.**

---

## Component identity

`braink:restart` version `1.0.0`. Public names: `RestartState`,
`RestartManager`.

## Purpose

Prove — by execution rather than assertion — that a runtime session can die,
cleanly or otherwise, and that a new process can pick up the same ledger with an
unbroken hash chain and a truthful account of what happened in between.

## Inputs

* `state_path: str` and `ledger_path: str` (both required; empty raises
  `ValueError`), plus an optional `session_id` (default `uuid4().hex`).
* A live `Ledger` instance for `save_state`, `recover`,
  `simulate_unclean_shutdown` and `generate_restart_receipt`.

## Outputs

* `RestartState(session_id, last_entry_id, last_entry_hash, ledger_path,
  timestamp, clean_shutdown)` persisted as pretty-printed, key-sorted JSON.
* `recover()` report dict.
* `generate_restart_receipt()` proof dict.
* A `CRASH_SIMULATED` ledger entry from `simulate_unclean_shutdown`.

## Dependencies

`braink_runtime.ledger`; stdlib `json`, `os`, `uuid`, `dataclasses`, `datetime`.

## Interfaces

```python
manager = RestartManager("state.json", "ledger.sqlite", session_id="s1")
state   = manager.save_state(ledger, clean=True)
manager.simulate_unclean_shutdown(ledger)     # appends CRASH_SIMULATED
loaded  = manager.load_state()                # RestartState | None
report  = manager.recover(reopened_ledger)
receipt = manager.generate_restart_receipt(reopened_ledger, loaded)
```

## Reconstruction rules

1. **`save_state`** snapshots `ledger.head_id()` and `ledger.head_hash()` into a
   `RestartState`, creates the parent directory if needed, and writes JSON with
   `indent=2, sort_keys=True` so that the file diffs cleanly. The marker is
   small and independent of the ledger on purpose: it is the *claim* against
   which the ledger is later checked.
2. **`load_state`** returns `None` when the file is absent, when it is not valid
   JSON, or when required keys are missing or malformed. It never raises. A
   missing or corrupt marker is a normal condition after a crash, not an error.
3. **`simulate_unclean_shutdown`** appends a `CRASH_SIMULATED` event carrying the
   session id and a reason, and then **deliberately does not save state**. That
   is what makes it a simulation of an unclean exit: the ledger moves ahead of
   the marker.
4. **`recover`** loads the marker, calls `verify_chain()` and `detect_tamper()`
   on the supplied ledger, and reports `state_found`, `clean_shutdown`,
   `saved_entry_id`, `saved_entry_hash`, `current_entry_id`,
   `current_entry_hash`, `entries_since_saved_state` (`head_id - saved id`, or
   `head_id` when there is no marker), `chain_valid`, `tampered_entries`,
   `recovery_ok` and a `status` of `RESTART_TESTED` or `RECOVERY_FAILED`.
   `entries_since_saved_state` is the important number: it quantifies exactly how
   much work happened after the last clean checkpoint, so a crash is *measured*
   rather than merely noticed.
5. **`generate_restart_receipt`** runs `recover`, then wraps it with
   `receipt_type = "RESTART_PROOF"`, the pre-restart state, the post-restart head
   id and hash, the entry count, and `continuity_proven`, which is true only when
   a marker existed, the chain verifies, and the head id has not gone *backwards*
   relative to the marker. A ledger that shrank is the one thing recovery must
   never call continuous.

## Required skill or skillset

`crash-recovery-proof`, skillset `durability-and-proof`.

## Conceptual validation method

Recovery compares an independently persisted head hash against the hash chain
recomputed from the database. Divergence is therefore impossible to hide: either
the recomputed chain matches the marker's head, or the difference is reported as
a measured gap, or the chain fails verification outright. There is no path in
which recovery reports success over a broken chain.

## Practical validation method

`tests/test_restart.py` — 10 tests: `save_state` writes the expected JSON;
`load_state` round-trips it exactly; missing file returns `None`; corrupt file
returns `None`; recovery over a reopened ledger reports a valid chain, no
tampering and a zero gap; `simulate_unclean_shutdown` appends `CRASH_SIMULATED`
and produces `entries_since_saved_state == 1`; post-crash integrity holds and new
appends continue the chain at the right id; the receipt contains all fourteen
required fields with `continuity_proven` true; recovery without a marker is
handled; constructor guards raise. `scripts/test_restart.command` runs the same
sequence live, and `tests/test_end_to_end.py::test_restart_preserves_ledger_integrity`
does it through the full `BrAInKRuntime`.

## Current validation state

**RESTART_TESTED.** A second `Ledger` object over the same file, in the same
process, after a simulated crash, verifies the chain and resumes correctly.

## Evidence generated

`evidence/RESTART_RECEIPT.json` (real session, real hashes, `continuity_proven`),
`evidence/TEST_RESULTS.json`.

## Saved representations

`src/braink_runtime/restart.py`, this document,
`scripts/test_restart.command`, `registry/COMPONENT_REGISTRY.json`.

## Remaining limitations or gates

* **Simulated, not real.** The crash is a code path, not a `SIGKILL` and not a
  power cut. A true durability claim needs an OS-level kill during an in-flight
  write, and ideally a host-level power-loss test.
* The marker file is neither signed nor hash-chained, so an attacker who can
  edit the ledger can also edit the marker to agree with it.
* Recovery is read-only: it reports damage, it does not repair or truncate.
* No leader election or lock file, so two processes recovering the same ledger
  concurrently is undefined.
