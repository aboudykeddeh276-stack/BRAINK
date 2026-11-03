# Skill Map

Every component in `braink-runtime` 1.0.0, described with the full Rule 2 field
set and an honest Rule 3 status. This file is the index: the per-subsystem
documents in `docs/` expand each entry into reconstruction-grade prose.

Status vocabulary in ascending order of strength:
`DEFINED` → `IMPLEMENTED` → `UNIT_TESTED` → `INTEGRATION_TESTED` →
`RESTART_TESTED` → `LOCALLY_EXECUTED` → `LOCALLY_PROVEN` →
`EXTERNALLY_OBSERVED` → `PUBLICLY_DEPLOYED` → `PRODUCTION_VALIDATED`.
**Nothing in this package exceeds `LOCALLY_PROVEN`.**

---

## canonical

### Component identity

`braink:canonical` version `1.0.0`  
Module: `src/braink_runtime/canonical.py`  
Id: `7bca708011009a2f0534be3f017ef3a65448bc1cfc6fbdf732730e54d8bce49f`

### Purpose

Deterministic JSON serialization and SHA-256 hashing used by every other component so that identical logical objects always hash identically.

### Inputs

* python dict

### Outputs

* canonical JSON string
* UTF-8 bytes
* sha256 hex digest
* namespaced key string

### Dependencies

* `python:json`
* `python:hashlib`

### Interfaces

* canonical_serialize(obj)
* canonical_bytes(obj)
* canonical_hash(obj)
* stable_namespace(namespace,name)

### Required skill or skillset

`deterministic-serialization`

### Conceptual validation method

Argue key-order independence and byte stability from the JSON dump parameters (sort_keys, tight separators, ensure_ascii).

### Practical validation method

pytest assertions that reordered dicts serialize and hash identically and that digests are 64 hex chars.

### Current validation state

**UNIT_TESTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* tests/test_identity.py

### Saved representations

* src/braink_runtime/canonical.py
* docs/IDENTITY_MAPPING.md

### Remaining limitations or gates

* Only dict roots are accepted.
* Non-JSON-native values are coerced via str() and are therefore lossy.

---

## linguistic_core

### Component identity

`braink:linguistic_core` version `1.0.0`  
Module: `src/braink_runtime/linguistic_core.py`  
Id: `3fd83fb16d5b1dac712447108e011c182b9e58da540cf0c05294c97a970ead71`

### Purpose

Normalise free text and map it deterministically onto a closed set of runtime intents; the only component permitted to read raw text.

### Inputs

* utf-8 text (1..4096 chars)
* token lists

### Outputs

* normalised text
* token list
* intent mapping dict
* ambiguity score dict

### Dependencies

* `python:re`
* `python:dataclasses`

### Interfaces

* normalize(text)
* tokenize(text)
* map_intent(text)
* validate_token(token)
* handle_ambiguity(tokens)
* lexicon_version()

### Required skill or skillset

`deterministic-intent-mapping`

### Conceptual validation method

Show the mapping is a pure function of (lexicon version, normalised tokens) with no clock, randomness or I/O.

### Practical validation method

pytest coverage of normalisation, tokenisation, all five intents, UNKNOWN fallback, token validation bounds and ValueError guards.

### Current validation state

**UNIT_TESTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* tests/test_linguistic_core.py

### Saved representations

* src/braink_runtime/linguistic_core.py
* docs/LINGUISTIC_CORE.md

### Remaining limitations or gates

* Lexicon is small and English-only.
* No syntax, negation or multi-clause handling.

---

## identity

### Component identity

`braink:identity` version `1.0.0`  
Module: `src/braink_runtime/identity.py`  
Id: `346576e4dcc3f03f7ceee89826f516477e498245e82f8faefa8e567ba563f6cc`

### Purpose

Derive collision-resistant identities for components, skills and services and refuse to let one identity denote two different input tuples.

### Inputs

* namespace
* name
* version
* skill name
* service endpoint

### Outputs

* 64-hex identity strings
* registry records
* CollisionError

### Dependencies

* `braink:canonical`

### Interfaces

* generate_component_id()
* generate_skill_id()
* generate_service_id()
* detect_collision()
* IdentityRegistry.register()

### Required skill or skillset

`deterministic-identity`

### Conceptual validation method

Identity is SHA-256 over a canonical tuple; collision resistance reduces to SHA-256 preimage/collision resistance.

### Practical validation method

pytest determinism, distinctness, collision detection and CollisionError-on-conflict tests.

### Current validation state

**UNIT_TESTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* tests/test_identity.py

### Saved representations

* src/braink_runtime/identity.py
* docs/IDENTITY_MAPPING.md

### Remaining limitations or gates

* Registry is in-memory only and is not persisted across processes.

---

## ledger

### Component identity

`braink:ledger` version `1.0.0`  
Module: `src/braink_runtime/ledger.py`  
Id: `a3e4db40fd2ec828cde57d87289520585c577949eb600745ed5bd75584ae6ba9`

### Purpose

Append-only SQLite event log whose entries form a SHA-256 hash chain, giving tamper evidence and restart continuity.

### Inputs

* event_type string
* payload dict
* sqlite file path

### Outputs

* LedgerEntry records
* chain verification boolean
* tampered entry id list
* integrity receipt

### Dependencies

* `python:sqlite3`
* `braink:canonical`

### Interfaces

* append()
* verify_chain()
* detect_tamper()
* get_all()
* export_receipt()
* close()

### Required skill or skillset

`tamper-evident-logging`

### Conceptual validation method

Each entry hash covers the previous hash, so any mutation invalidates every subsequent link.

### Practical validation method

pytest appends, reopen-continues-chain, direct SQL corruption of payload and of entry_hash, both detected.

### Current validation state

**LOCALLY_PROVEN**

### Evidence generated

* evidence/TEST_RESULTS.json
* evidence/LEDGER_INTEGRITY_RECEIPT.json
* tests/test_ledger.py

### Saved representations

* src/braink_runtime/ledger.py
* docs/LEDGER_DURABILITY.md
* schemas/ledger-event.schema.json

### Remaining limitations or gates

* Tamper evidence, not tamper prevention: a writer with DB access can rewrite the whole chain unless the root hash is externally anchored.
* No external anchoring is performed in this package.

---

## signer

### Component identity

`braink:signer` version `1.0.0`  
Module: `src/braink_runtime/signer.py`  
Id: `e8911ec56ced41f1acb58a398184260875aae60ca16ec24eab283fb210bd226f`

### Purpose

Provide a proven local signing path (HMAC over the canonical payload) and an explicitly unimplemented production signing boundary.

### Inputs

* payload dict
* signature envelope

### Outputs

* SignatureEnvelope
* verification boolean
* NotImplementedError for production path

### Dependencies

* `python:hmac`
* `python:hashlib`
* `braink:canonical`

### Interfaces

* TestSigner.sign()
* TestSigner.verify()
* ProductionSignerPlaceholder.sign()
* prepare_canonical_payload()

### Required skill or skillset

`payload-authentication`

### Conceptual validation method

Signing over canonical bytes means semantically identical payloads verify and any mutation fails; the production path is intentionally fail-closed.

### Practical validation method

pytest sign/verify round trip, tampered payload, tampered signature, wrong key, NotImplementedError assertions.

### Current validation state

**LOCALLY_PROVEN**

### Evidence generated

* evidence/TEST_RESULTS.json
* tests/test_signer.py

### Saved representations

* src/braink_runtime/signer.py
* docs/SIGNER_BOUNDARY.md
* config/signer.example.json

### Remaining limitations or gates

* TestSigner uses a published symmetric key and provides no non-repudiation.
* ProductionSignerPlaceholder is DEFINED only and cannot become PRODUCTION_VALIDATED without real KMS/HSM key infrastructure.

---

## dns_transport

### Component identity

`braink:dns_transport` version `1.0.0`  
Module: `src/braink_runtime/dns_transport.py`  
Id: `94cbbfcf7364b9d764cf729bdbc01b417c8660b87422cb731dd28ed22c5f2d53`

### Purpose

Build and parse DNS messages on the wire and query resolvers over UDP with TCP fallback, emitting honestly capped proof receipts.

### Inputs

* domain name
* record type
* resolver address
* timeout

### Outputs

* DNSRecord list
* DNSProofReceipt
* status string

### Dependencies

* `python:socket`
* `python:struct`

### Interfaces

* build_query()
* parse_response()
* query_udp()
* query_tcp()
* generate_proof_receipt()

### Required skill or skillset

`raw-protocol-transport`

### Conceptual validation method

Header, question and answer encodings are checked against RFC 1035 field layout including label compression pointers.

### Practical validation method

pytest byte-level header assertions plus parsing of synthetic A, TXT, multi-answer and CNAME responses through a mocked socket; live failure path exercised against TEST-NET-3.

### Current validation state

**LOCALLY_EXECUTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* evidence/DNS_PROOF_RECEIPT.json
* tests/test_dns_transport.py

### Saved representations

* src/braink_runtime/dns_transport.py
* docs/DNS_TRANSPORT.md
* schemas/dns-proof.schema.json
* config/dns_records.json

### Remaining limitations or gates

* Authoritative external DNS confirmation is NOT possible from the sandbox; status is capped at LOCALLY_EXECUTED.
* No DNSSEC validation.
* EDNS0 is not implemented.

---

## restart

### Component identity

`braink:restart` version `1.0.0`  
Module: `src/braink_runtime/restart.py`  
Id: `ccea6ae070ee13ff568013dd040f8c8f30872dd3b000c99b82a77b5db488089e`

### Purpose

Persist a restart marker, simulate unclean shutdown and prove that the ledger chain survives process death intact.

### Inputs

* state file path
* ledger path
* Ledger instance

### Outputs

* RestartState JSON
* recovery report
* restart proof receipt

### Dependencies

* `braink:ledger`
* `python:json`
* `python:uuid`

### Interfaces

* save_state()
* load_state()
* recover()
* simulate_unclean_shutdown()
* generate_restart_receipt()

### Required skill or skillset

`crash-recovery-proof`

### Conceptual validation method

Recovery compares the persisted head hash against the recomputed chain head, so silent divergence is impossible.

### Practical validation method

pytest save/load round trip, crash simulation, reopen-and-verify, continuity_proven assertions.

### Current validation state

**RESTART_TESTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* evidence/RESTART_RECEIPT.json
* tests/test_restart.py

### Saved representations

* src/braink_runtime/restart.py
* docs/RESTART_AND_RECOVERY.md

### Remaining limitations or gates

* Restart is simulated in-process; no OS-level kill -9 or power-loss test is performed.
* Marker file is not itself signed.

---

## runtime

### Component identity

`braink:runtime` version `1.0.0`  
Module: `src/braink_runtime/runtime.py`  
Id: `485f747c3579b6baf37ba0188384358db2bbdd36391a25f135729ba648f92f34`

### Purpose

Orchestrate every subsystem into one lifecycle: start, process commands, report status, shut down cleanly and resume.

### Inputs

* config dict
* command text

### Outputs

* status dicts
* ledger entries
* signature envelopes
* restart state

### Dependencies

* `braink:linguistic_core`
* `braink:identity`
* `braink:ledger`
* `braink:signer`
* `braink:dns_transport`
* `braink:restart`

### Interfaces

* BrAInKRuntime.start()
* process_command()
* shutdown()
* get_status()

### Required skill or skillset

`runtime-orchestration`

### Conceptual validation method

Every externally visible action produces exactly one ledger entry, so the ledger is a complete trace of the session.

### Practical validation method

pytest end-to-end lifecycle, malformed command handling, restart-and-resume with chain verification.

### Current validation state

**INTEGRATION_TESTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* tests/test_end_to_end.py

### Saved representations

* src/braink_runtime/runtime.py
* docs/ARCHITECTURE.md

### Remaining limitations or gates

* Single-process, single-threaded.
* No network listener and no authentication of the caller.

---

## receipts

### Component identity

`braink:receipts` version `1.0.0`  
Module: `src/braink_runtime/receipts.py`  
Id: `4ac7c68a2f2c505c3e233a426696d001e0588846cec9c4874a4267fe9d72405a`

### Purpose

Turn execution outcomes into durable evidence artefacts: package manifests, test result records and validation receipts.

### Inputs

* package root path
* test counters
* component id
* evidence dict

### Outputs

* manifest dict
* test result dict
* validation receipt dict

### Dependencies

* `python:os`
* `python:hashlib`
* `braink:canonical`

### Interfaces

* generate_package_manifest()
* generate_test_results()
* generate_validation_receipt()
* sha256_file()

### Required skill or skillset

`evidence-generation`

### Conceptual validation method

Manifest hashing is a pure function of file bytes, so any file edit changes the manifest hash.

### Practical validation method

pytest manifest over a temp tree, stability across repeated runs, PASSED/FAILED status logic, argument guards.

### Current validation state

**UNIT_TESTED**

### Evidence generated

* evidence/TEST_RESULTS.json
* evidence/PACKAGE_MANIFEST.json
* tests/test_end_to_end.py

### Saved representations

* src/braink_runtime/receipts.py
* docs/ARCHITECTURE.md
* schemas/validation-receipt.schema.json

### Remaining limitations or gates

* Manifest excludes caches and compiled artefacts.
* Receipts are not externally notarised.

---

## Skillsets

| Skillset | Skills | Aggregate status |
|---|---|---|
| `determinism-core` | `deterministic-serialization`, `deterministic-identity` | UNIT_TESTED |
| `language-surface` | `deterministic-intent-mapping` | UNIT_TESTED |
| `durability-and-proof` | `tamper-evident-logging`, `crash-recovery-proof`, `evidence-generation` | LOCALLY_PROVEN |
| `trust-boundary` | `payload-authentication`, `raw-protocol-transport` | BOUNDED |
| `orchestration` | `runtime-orchestration` | INTEGRATION_TESTED |

Aggregate status is the floor of member skill statuses; 'BOUNDED' marks a skillset whose ceiling is set by an explicit proof boundary rather than by test coverage.
