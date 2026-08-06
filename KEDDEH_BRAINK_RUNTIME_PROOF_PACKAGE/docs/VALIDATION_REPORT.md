# Validation Report

Package: `braink-runtime` 1.0.0
Scope: the nine modules under `src/braink_runtime/`.
Method: real execution. Every status below is backed by a test that was run, or
is explicitly marked as an open gate.

---

## 1. Per-component status

| Component | Status | Unit | Integration | Restart | Locally proven | Externally observed |
|---|---|:--:|:--:|:--:|:--:|:--:|
| `canonical` | UNIT_TESTED | ✅ | ✅ | — | — | ❌ |
| `linguistic_core` | UNIT_TESTED | ✅ | ✅ | — | — | ❌ |
| `identity` | UNIT_TESTED | ✅ | ✅ | — | — | ❌ |
| `ledger` | LOCALLY_PROVEN | ✅ | ✅ | ✅ | ✅ | ❌ |
| `signer` (TestSigner) | LOCALLY_PROVEN | ✅ | ✅ | — | ✅ | ❌ |
| `signer` (Production) | **DEFINED** | ✅ (fails closed) | — | — | ❌ | ❌ |
| `dns_transport` | **LOCALLY_EXECUTED** | ✅ | — | — | ❌ | ❌ |
| `restart` | RESTART_TESTED | ✅ | ✅ | ✅ | ✅ | ❌ |
| `runtime` | INTEGRATION_TESTED | ✅ | ✅ | ✅ | — | ❌ |
| `receipts` | UNIT_TESTED | ✅ | ✅ | — | — | ❌ |

The machine-readable form of this table is `registry/VALIDATION_MATRIX.csv`.
The **Externally observed** column is `❌` for every row, without exception.

## 2. What was actually executed

* `python -m pytest tests/ -v --tb=short` from the package root — **116 tests,
  all passing**. The captured result, including every test name, is in
  `evidence/TEST_RESULTS.json`, together with the real pytest exit code.
* A ledger was created, three events appended, the chain verified and a receipt
  exported with real SHA-256 hashes → `evidence/LEDGER_INTEGRITY_RECEIPT.json`.
* A ledger was deliberately corrupted with direct SQL and the corruption was
  detected (`scripts/verify_ledger.command`, and two tests in
  `tests/test_ledger.py`).
* A session was started, a command processed, state saved, an unclean shutdown
  simulated, the ledger reopened and the chain re-verified →
  `evidence/RESTART_RECEIPT.json`.
* A DNS query was built and executed locally, with the exact wire bytes recorded
  → `evidence/DNS_PROOF_RECEIPT.json`.
* Every file in the package was hashed → `evidence/PACKAGE_MANIFEST.json`.

## 3. DNS proof boundary — explicit

**Authoritative external DNS confirmation is NOT possible from this sandbox.
The DNS status is capped at `LOCALLY_EXECUTED`.**

What is proven: the query builder emits RFC 1035 conformant bytes (asserted at
the byte level), the parser correctly decodes `A`, `TXT`, `CNAME` and
multi-answer responses including compression pointers (asserted against
synthetic packets), and a query is genuinely transmitted over a real socket.

What is **not** proven, and cannot be proven here:

* that a specific authoritative nameserver replied,
* that any record is published in the public DNS,
* that any third party can observe the same answer.

Structural enforcement: `MAX_PROOF_STATUS = "LOCALLY_EXECUTED"`; every receipt
sets `authoritative = False` and `authoritative_external_confirmed = false`;
`schemas/dns-proof.schema.json` does not include `EXTERNALLY_OBSERVED` or
`PUBLICLY_DEPLOYED` in its status enum;
`tests/test_dns_transport.py::test_generate_proof_receipt_status_is_capped`
asserts the cap. Closing this gate requires an independent external observer.

## 4. Signer proof boundary — explicit

**`TestSigner` is LOCALLY_PROVEN. `ProductionSignerPlaceholder` is DEFINED and
cannot become PRODUCTION_VALIDATED without real key infrastructure.**

`TestSigner` uses a symmetric HMAC key that is published in the source and
labelled `NOT A SECRET`. It proves the signing and verification code path — sign,
verify, reject tampered payloads, reject tampered signatures, reject the wrong
key — and it proves nothing about authenticity, because everybody has the key.

`ProductionSignerPlaceholder` holds no key and raises `NotImplementedError` from
both `sign` and `verify`. It fails closed by design. Closing this gate requires
HSM- or KMS-held key material, an attested custody process, asymmetric signing,
and verification performed by a party that is not this package.

## 5. Other open gates

| Gate | Component | What would close it |
|---|---|---|
| No external anchoring of the ledger root hash | `ledger` | Publishing the root hash to a medium the operator cannot rewrite |
| Crash is simulated in-process | `restart` | OS-level `SIGKILL` mid-write, plus a power-loss test |
| Registry is in-memory | `identity` | Persisted, signed identity store with cross-process collision detection |
| Single-process runtime | `runtime` | Concurrency control, locking and a multi-writer test |
| Receipts are self-attested | `receipts` | Third-party notarisation or a trusted timestamp |
| Lexicon is minimal and English-only | `linguistic_core` | A versioned, reviewed lexicon with negation and syntax handling |

## 6. Reproduction

```bash
cd KEDDEH_BRAINK_RUNTIME_PROOF_PACKAGE
python -m pip install pytest
./scripts/run_tests.command          # 116 tests
./scripts/verify_ledger.command      # positive and negative ledger controls
./scripts/test_restart.command       # crash / restart / recovery
./scripts/verify_dns.command         # local DNS execution, capped status
./scripts/generate_receipt.command   # rewrite every file in evidence/
```

Regenerating the evidence overwrites `evidence/*.json` with new timestamps and
hashes. The `manifest_hash` in `evidence/PACKAGE_MANIFEST.json` excludes the
timestamp, so it changes only when file content actually changes.

## 7. Statement

No component in this package claims `EXTERNALLY_OBSERVED`, `PUBLICLY_DEPLOYED`
or `PRODUCTION_VALIDATED`. Where a claim could not be earned by execution inside
this environment, the gate has been left open and named rather than closed by
assertion.
