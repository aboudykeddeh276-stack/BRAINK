# Ledger Durability

Covers: `src/braink_runtime/ledger.py`.
**Status: RESTART_TESTED / LOCALLY_PROVEN.**

---

## Component identity

`braink:ledger` version `1.0.0`. Public names: `Ledger`, `LedgerEntry`,
`GENESIS_HASH = "GENESIS"`.

## Purpose

Give the runtime a durable, append-only record of everything that happened, in
order, such that any later mutation of any entry is detectable, and such that the
record survives process death intact.

## Inputs

* `db_path: str` — SQLite file path; empty raises `ValueError`.
* `append(event_type: str, payload: dict)` — an empty `event_type` or a non-dict
  payload raises `ValueError`; a `None` payload is coerced to `{}`.

## Outputs

* `LedgerEntry(entry_id, event_type, payload, prev_hash, entry_hash, timestamp)`.
* `verify_chain() -> bool`, `detect_tamper() -> list[int]`,
  `get_all() -> list[LedgerEntry]`, `get(entry_id)`, `count()`,
  `head_hash()`, `head_id()`.
* `export_receipt() -> dict` with `receipt_type`, `ledger_path`, `entry_count`,
  `genesis_hash`, `root_hash`, `hashes`, `event_types`, `chain_valid`,
  `tampered_entries`, `generated_at`, `status`.
* Persisted side effect: rows in the `ledger` table.

## Dependencies

Stdlib `sqlite3`, `json`, `dataclasses`, `datetime`; `braink_runtime.canonical`.

## Interfaces

```python
ledger = Ledger("/path/ledger.sqlite")
entry = ledger.append("RUNTIME_START", {"session_id": "abc"})
ledger.verify_chain()      # True
ledger.detect_tamper()     # []
ledger.export_receipt()
ledger.close()
with Ledger(path) as l:    # context manager closes on exit
    l.append("EVENT", {})
```

## Reconstruction rules

1. **Schema.**
   ```sql
   CREATE TABLE IF NOT EXISTS ledger (
       entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
       event_type TEXT NOT NULL,
       payload    TEXT NOT NULL,
       prev_hash  TEXT NOT NULL,
       entry_hash TEXT NOT NULL,
       timestamp  TEXT NOT NULL
   );
   ```
   Open with `row_factory = sqlite3.Row` and `PRAGMA journal_mode=WAL` so that a
   crash mid-write leaves a recoverable file rather than a torn page.
2. **Hash rule.**
   `entry_hash = sha256(canonical_serialize({entry_id, event_type, payload,
   prev_hash, timestamp}))`. Note that `entry_hash` is not part of its own
   preimage, and that `prev_hash` is, which is what creates the chain.
3. **Genesis.** The first entry's `prev_hash` is the literal string `"GENESIS"`,
   not a digest. This makes an empty ledger and a truncated ledger
   distinguishable: a chain that begins with anything else is invalid.
4. **Append.** Read the head row; `prev_hash = head.entry_hash or "GENESIS"`,
   `entry_id = head.entry_id + 1 or 1`. Timestamp with
   `datetime.now(timezone.utc).isoformat()`. Compute the hash, then `INSERT` and
   `COMMIT` — the commit is what makes durability real; without it the entry
   exists only in the connection.
5. **Payload storage.** Payloads are stored as `json.dumps(payload,
   sort_keys=True, separators=(",", ":"))` so the stored text round-trips into a
   dict that re-canonicalises to the same bytes.
6. **`verify_chain`.** Walk entries in ascending id. Require `entry_id ==
   expected_id` (starting at 1), `prev_hash == expected_prev` (starting at
   `"GENESIS"`) and `compute_hash() == entry_hash`. Advance `expected_prev` to
   the current `entry_hash`. Any failure returns `False`. An empty ledger is
   valid.
7. **`detect_tamper`.** Same walk, but collect ids instead of returning early, so
   the caller learns *where* the damage is. An entry is reported when its stored
   hash does not recompute, or when its `prev_hash` does not match the previous
   entry's hash. Deleting a middle row therefore surfaces as a broken link at the
   following row.
8. **Reopen behaviour.** Nothing is cached in memory: `head_hash()` and
   `head_id()` always read the table. Re-instantiating `Ledger` on the same path
   therefore continues the chain automatically, which is exactly what restart
   recovery relies on.

## Required skill or skillset

`tamper-evident-logging`, skillset `durability-and-proof`.

## Conceptual validation method

Each entry's hash covers the previous entry's hash. By induction, altering entry
*k* changes `entry_hash(k)`, which invalidates `prev_hash(k+1)`, and so on to the
head. Therefore an attacker who edits history must rewrite every subsequent entry
*and* must control the published root hash. Detection of a single-row edit is
unconditional given only the recomputation, with no external state required.

## Practical validation method

`tests/test_ledger.py` — 15 tests: genesis linkage, successive linkage, chain
verification over five entries, empty-ledger validity, `get_all`/`get`,
**direct SQL corruption of a payload** (detected), **direct SQL corruption of an
`entry_hash`** (detected), reopen-continues-chain, receipt structure, distinct
hashes for byte-identical duplicate events (the timestamp and id differ),
argument guards, path guard and the context manager. Additionally
`scripts/verify_ledger.command` performs a live positive-and-negative control
run, and `tests/test_restart.py` proves the chain across a simulated crash.

## Current validation state

**RESTART_TESTED / LOCALLY_PROVEN.** Proven locally: the tamper-detection and
restart-continuity claims are demonstrated by executing code, not asserted.

## Evidence generated

`evidence/LEDGER_INTEGRITY_RECEIPT.json` (real hashes from a real run),
`evidence/RESTART_RECEIPT.json`, `evidence/TEST_RESULTS.json`.

## Saved representations

`src/braink_runtime/ledger.py`, this document,
`schemas/ledger-event.schema.json`, `scripts/verify_ledger.command`,
`registry/COMPONENT_REGISTRY.json`.

## Remaining limitations or gates

* **Tamper evidence, not tamper prevention.** Anyone with write access to the
  SQLite file can rewrite the entire chain consistently. The only real defence is
  publishing the root hash somewhere the attacker does not control; **no external
  anchoring is performed by this package**, so that gate remains open.
* No concurrency control: two processes appending to the same file may interleave
  ids. Single-writer use is assumed.
* Timestamps come from the local clock and are not attested; they order nothing
  that the `entry_id` does not already order.
* Payloads are not encrypted. Do not put secrets in ledger payloads.
* Durability is SQLite's durability: it survives process death, and survives
  power loss only as far as the filesystem's `fsync` semantics allow.
