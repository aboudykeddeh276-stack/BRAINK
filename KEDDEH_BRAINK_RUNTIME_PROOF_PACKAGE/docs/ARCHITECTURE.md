# BrAInK Runtime — Architecture

Covers: `src/braink_runtime/runtime.py` and `src/braink_runtime/receipts.py`.
This document is written as a **reconstruction substrate**: an engineer or an AI
should be able to rebuild both modules from this prose alone, without reading the
source.

---

## 1. System diagram

```
                       +-------------------------------------+
   free text  ───────► |         linguistic_core             |
   "run diagnostics"   |  normalize → tokenize → map_intent  |
                       +------------------+------------------+
                                          │ {intent, tokens, confidence}
                                          ▼
 +-----------+     +--------------------------------------------------+
 | identity  |◄────|                    runtime                        |
 | registry  |     |   BrAInKRuntime: start / process_command /        |
 +-----------+     |   get_status / shutdown                           |
                   +---+---------------+---------------+--------------+
                       │               │               │
                       ▼               ▼               ▼
                 +-----------+   +-----------+   +--------------+
                 |  ledger   |   |  signer   |   | dns_transport|
                 | sqlite3   |   | HMAC test |   | UDP + TCP    |
                 | hash chain|   | prod=STUB |   | RFC1035 wire |
                 +-----+-----+   +-----------+   +--------------+
                       │
                       ▼
                 +-----------+           +---------------------------+
                 |  restart  | ────────► |         receipts          |
                 | state.json|           | manifest / tests / proofs |
                 +-----------+           +-------------+-------------+
                                                       │
                                                       ▼
                                                  evidence/*.json

  canonical.py sits underneath everything: every hash in the diagram is
  sha256(canonical_serialize(obj)).
```

Data flow invariant: **text enters only through `linguistic_core`, and every
externally visible action leaves a ledger entry.** The ledger is therefore a
complete, ordered, tamper-evident trace of a session.

---

## 2. Component: `runtime.py`

### Component identity
`braink:runtime` version `1.0.0`; id = `sha256(canonical_serialize({"name":"runtime","namespace":"braink","version":"1.0.0"}))`.
Class: `BrAInKRuntime`. Constant: `DEFAULT_NAMESPACE = "braink"`.

### Purpose
Compose the six functional subsystems into a single, auditable lifecycle so that
no subsystem has to know about any other. The runtime owns construction order,
error containment and the guarantee that every action is ledgered.

### Inputs
* `config: dict` with optional keys `ledger_path`, `state_path`, `namespace`,
  `version`, `session_id`. A non-dict or `None` config raises `ValueError`.
* `text: str` passed to `process_command`.

### Outputs
* `start() -> dict` — `status`, `session_id`, `runtime_id`, `entry_id`,
  `entry_hash`, `signature`, `started_at`.
* `process_command(text) -> dict` — `accepted`, `intent`, `tokens`,
  `confidence`, `error`, `entry_id`, `entry_hash`, `signature`.
* `shutdown(clean) -> dict` — `status`, `clean`, `session_id`, `last_entry_id`,
  `last_entry_hash`, `chain_valid`, `shutdown_at`.
* `get_status() -> dict` — nested per-subsystem state (see §2.7).
* Side effects: ledger rows, a restart state file.

### Dependencies
`braink_runtime.linguistic_core`, `.identity`, `.ledger`, `.signer`,
`.dns_transport`, `.restart`. Standard library: `os`, `uuid`, `datetime`.

### Interfaces
`BrAInKRuntime(config)`, `.start()`, `.process_command(text)`,
`.shutdown(clean=True)`, `.get_status()`. Public attributes: `linguistic`,
`identities`, `ledger`, `signer`, `production_signer`, `dns`,
`restart_manager`, `runtime_id`, `session_id`, `started`, `command_count`.

### Required skill or skillset
`runtime-orchestration` (skillset `orchestration`).

### Reconstruction rules

1. **Construction.** Copy the config. Resolve `namespace` (default `braink`),
   `version` (default `1.0.0`), `session_id` (default `uuid4().hex`),
   `ledger_path` (default `<cwd>/braink_ledger.sqlite`) and `state_path`
   (default `restart_state.json` beside the ledger). Instantiate
   `LinguisticCore()`, `IdentityRegistry()`, `Ledger(ledger_path)`,
   `TestSigner()`, `ProductionSignerPlaceholder()`, `DNSTransport()` and
   `RestartManager(state_path, ledger_path, session_id)`. Compute
   `runtime_id = generate_component_id(namespace, "runtime", version)` and
   register it in the identity registry with its input tuple. Set
   `started = False`, `command_count = 0`.
2. **`start()`.** Build the payload `{session_id, runtime_id, version,
   lexicon_version}`, append it as a `RUNTIME_START` ledger event, sign the same
   payload with `TestSigner`, set `started = True` and return the status dict.
   The signature covers the payload, not the ledger row, so it stays valid
   independently of entry ordering.
3. **`process_command(text)`.** Raise `RuntimeError` if not started. Call
   `map_intent(text)` inside a `try`; on `ValueError` (malformed input) set
   `intent = "INVALID"`, `accepted = False` and keep the error string —
   **rejected input is still ledgered**, because refusing to log rejections
   would let an attacker erase their probes. Increment `command_count`. Append a
   `COMMAND` event whose payload is `{session_id, command_index, raw_length,
   intent, tokens, confidence, accepted, error}`. Note that the raw text is
   *never* stored, only its length: the ledger must not become a copy of user
   input. Sign the payload and return.
4. **`shutdown(clean=True)`.** Append `RUNTIME_SHUTDOWN` with `{session_id,
   clean}`, call `RestartManager.save_state(ledger, clean)`, build the receipt
   including `chain_valid`, close the ledger and set `started = False`.
5. **`get_status()`.** Return a nested dict with keys `session_id`,
   `runtime_id`, `version`, `started`, `commands_processed`, `linguistic_core`,
   `identity`, `ledger`, `signer`, `dns`, `restart`, `reported_at`. The `ledger`
   block is produced by the helper `_ledger_status()`, which reports
   `{path, open: False, status: "CLOSED", note}` when the runtime is not started
   — after `shutdown()` the SQLite connection is closed, so querying it would
   raise `sqlite3.ProgrammingError`; status introspection must never be the thing
   that crashes. When started it reports `entry_count`, `head_hash` and
   `chain_valid`. The `dns` block must always report
   `status_cap: "LOCALLY_EXECUTED"` and `authoritative_external_confirmed:
   false`. The `signer` block must always report the production signer as
   `DEFINED`.

### Conceptual validation method
Argue completeness of the trace: `start`, every `process_command` and `shutdown`
each append exactly one entry, so `entry_count == 2 + command_count` for a clean
session. Argue containment: the only `except` clause catches `ValueError` from
the linguistic core, so no subsystem failure is silently swallowed.

### Practical validation method
`tests/test_end_to_end.py`: full lifecycle, unknown command, malformed command,
command-before-start, status-after-shutdown against a closed ledger,
restart-and-resume with chain verification, and a signed end-to-end proof
receipt.

### Current validation state
`INTEGRATION_TESTED`.

### Evidence generated
`evidence/TEST_RESULTS.json`, `evidence/RESTART_RECEIPT.json`.

### Saved representations
`src/braink_runtime/runtime.py`, this document,
`registry/COMPONENT_REGISTRY.json`.

### Remaining limitations or gates
Single-process and single-threaded; two runtimes sharing one ledger file are not
serialised. No network listener, no caller authentication, no back-pressure. The
runtime trusts its own config.

---

## 3. Component: `receipts.py`

### Component identity
`braink:receipts` version `1.0.0`.

### Purpose
Convert execution outcomes into durable artefacts that a third party can re-run
and compare byte for byte.

### Inputs
Package root path; test counters and names; component id, status and evidence
dict.

### Outputs
* `generate_package_manifest(root) -> {manifest_type, package_root,
  hash_algorithm, files{path: sha256}, file_count, generated_at, manifest_hash}`.
* `generate_test_results(passed, failed, errors, test_names, raw_summary) ->
  {receipt_type, status, timestamp, tests_run, passed, failed, errors,
  test_names, raw_summary}`.
* `generate_validation_receipt(component_id, status, evidence) ->
  {receipt_type, component_id, status, evidence, generated_at, receipt_hash}`.

### Dependencies
`braink_runtime.canonical`; stdlib `os`, `hashlib`, `datetime`.

### Interfaces
The three generators above plus `sha256_file(path, chunk_size=65536)` and the
constant `EXCLUDED_DIRS`.

### Required skill or skillset
`evidence-generation` (skillset `durability-and-proof`).

### Reconstruction rules
Walk the root with `os.walk`, pruning `__pycache__`, `.git`, `.pytest_cache`,
`.mypy_cache` and `node_modules` in place and skipping `.pyc`, `.pyo`,
`.sqlite-wal` and `.sqlite-shm`. Sort both directory and file names so the walk
order is deterministic. Store paths relative to the root with `/` separators.
Hash files in 64 KiB chunks so large files do not have to be resident. The
`manifest_hash` is `canonical_hash({"files": files})` — it deliberately excludes
the timestamp so that two runs over unchanged content produce the same manifest
hash. Test status is `PASSED` only when `failed == 0 and errors == 0 and
total > 0`; an empty run is `FAILED`, because "no tests ran" is not success.

### Conceptual validation method
Manifest hashing is a pure function of file bytes: any edit to any tracked file
changes at least one entry and therefore the manifest hash.

### Practical validation method
`tests/test_end_to_end.py::test_package_manifest_generation` builds a temp tree,
checks relative paths, digest length and stability across repeated runs;
`test_generate_test_results_status` checks the PASSED/FAILED rule;
`test_generate_validation_receipt_requires_fields` checks the guards.

### Current validation state
`UNIT_TESTED`.

### Evidence generated
`evidence/PACKAGE_MANIFEST.json`, `evidence/TEST_RESULTS.json`.

### Saved representations
`src/braink_runtime/receipts.py`, this document,
`schemas/validation-receipt.schema.json`.

### Remaining limitations or gates
The manifest excludes itself (it is written after the walk), so it proves the
state of everything *except* the manifest file. Receipts are self-attested: they
are not notarised, timestamped or anchored externally.

---

## 4. Failure model

| Failure | Detected by | Result |
|---|---|---|
| Malformed command text | `LinguisticCore` guards | `ValueError` caught, `INVALID` intent ledgered |
| Corrupted ledger row | `Ledger.detect_tamper()` | entry id returned, `verify_chain()` false |
| Process death mid-session | `RestartManager.recover()` | chain re-verified, gap reported |
| Resolver unreachable | `DNSTransport` socket guards | empty record list, `LOCAL_EXECUTION_FAILED` |
| Production signing attempted | `ProductionSignerPlaceholder` | `NotImplementedError`, fail-closed |

## 5. Honest proof ceiling

Nothing in this package exceeds `LOCALLY_PROVEN`. DNS is capped at
`LOCALLY_EXECUTED` and the production signer stays `DEFINED`. See
`docs/VALIDATION_REPORT.md`.
