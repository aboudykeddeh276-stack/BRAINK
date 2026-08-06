# KEDDEH BRAINK RUNTIME PROOF PACKAGE

`braink-runtime` **1.0.0** — a self-contained, standard-library-only Python
runtime that demonstrates, by execution rather than assertion, six primitives:
deterministic language intake, canonical identity, a tamper-evident ledger, a
bounded signing surface, raw DNS transport, and crash recovery.

---

## 1. Identity

| | |
|---|---|
| Package | `braink-runtime` |
| Version | `1.0.0` |
| Namespace | `braink` |
| Import root | `src/` (module `braink_runtime`) |
| Entry point | `braink_runtime.runtime:BrAInKRuntime` |
| Requires | Python ≥ 3.9, standard library only (`pytest` for tests) |
| Component ids | `sha256(canonical_serialize({namespace, name, version}))` — see `registry/COMPONENT_REGISTRY.json` |

## 2. Purpose

Most systems claim properties. This package tries to *earn* a small number of
them and to state precisely where the earning stops:

* **Determinism** — the same input always produces the same bytes, the same
  digests and the same identifiers (`canonical`, `identity`, `linguistic_core`).
* **Durability with tamper evidence** — every action is appended to a SHA-256
  hash chain in SQLite, and any later edit is detectable (`ledger`).
* **Recoverability** — a session can die and a new process can resume with the
  chain intact and the gap measured (`restart`).
* **Honest boundaries** — the two places where local execution cannot produce a
  real-world guarantee are marked, enforced in code and enforced in schema
  (`dns_transport`, `signer`).

## 3. Honest proof boundary

Read this before reading anything else.

### DNS

> **Authoritative external DNS confirmation is NOT possible from sandbox.
> Status capped at `LOCALLY_EXECUTED`.**

The wire format is proven byte by byte against synthetic packets and a query is
genuinely sent over a socket. What is *not* proven is that an authoritative
nameserver answered, or that any record is publicly published. `MAX_PROOF_STATUS`
is `"LOCALLY_EXECUTED"`, every receipt carries `authoritative: false` and
`authoritative_external_confirmed: false`, and
`schemas/dns-proof.schema.json` does not even contain `EXTERNALLY_OBSERVED` or
`PUBLICLY_DEPLOYED` as permitted values.

### Signer

> **`TestSigner` is `LOCALLY_PROVEN`. `ProductionSignerPlaceholder` is `DEFINED`
> and cannot become `PRODUCTION_VALIDATED` without real key infrastructure.**

`TestSigner` uses an HMAC key that is *published in the source and labelled as
not a secret*. It proves the code path and nothing about authenticity.
`ProductionSignerPlaceholder` holds no key and raises `NotImplementedError` from
both `sign` and `verify` — it fails closed on purpose.

No real secrets or private keys exist anywhere in this package, and none may be
added.

Full accounting: `docs/VALIDATION_REPORT.md`.

## 4. Layout

```
src/braink_runtime/   nine modules: canonical, linguistic_core, identity,
                      ledger, signer, dns_transport, restart, runtime, receipts
tests/                seven pytest modules, 116 tests
schemas/              JSON Schema draft-07 for every persisted structure
registry/             component / skill / skillset / discovery registries + CSV matrix
config/               example DNS records, example env, placeholder signer config
scripts/              five executable .command scripts
docs/                 nine reconstruction-grade documents
evidence/             receipts produced by really running the code
```

## 5. How to run the tests

```bash
cd KEDDEH_BRAINK_RUNTIME_PROOF_PACKAGE
python -m pip install pytest
python -m pytest tests/ -v          # pyproject sets pythonpath = ["src"]
```

or, equivalently:

```bash
./scripts/run_tests.command
```

Other scripts:

| Script | What it does |
|---|---|
| `scripts/run_tests.command` | Full pytest run |
| `scripts/verify_ledger.command` | Builds a ledger, verifies it, then corrupts it and proves detection |
| `scripts/test_restart.command` | Crash → restart → recovery sequence |
| `scripts/verify_dns.command` | Local DNS execution; prints wire bytes and a capped receipt |
| `scripts/generate_receipt.command` | Regenerates every file in `evidence/` from real runs |

## 6. Quick use

```python
import sys; sys.path.insert(0, "src")
from braink_runtime import BrAInKRuntime

runtime = BrAInKRuntime({"ledger_path": "./braink_ledger.sqlite"})
runtime.start()
print(runtime.process_command("run diagnostics"))   # -> intent EXECUTE
print(runtime.process_command("verify ledger"))     # -> intent VERIFY
print(runtime.get_status()["ledger"]["chain_valid"])
runtime.shutdown(clean=True)
```

## 7. How an AI should read this package

The prose in `docs/` is written to be a **reconstruction substrate**, not a
summary. It is intended to be sufficient, on its own, to rebuild the
implementation.

1. Start with `docs/ARCHITECTURE.md` for the system diagram, the data-flow
   invariant ("text enters only through the linguistic core; every action is
   ledgered") and the failure model.
2. Read `docs/SKILL_MAP.md` for all thirteen Rule 2 fields of all nine
   components in one place: *Component identity, Purpose, Inputs, Outputs,
   Dependencies, Interfaces, Required skill or skillset, Conceptual validation
   method, Practical validation method, Current validation state, Evidence
   generated, Saved representations, Remaining limitations or gates.*
3. Read the per-subsystem documents for the **Reconstruction rules** sections.
   Those sections state the exact algorithms — hash preimages, wire layouts,
   normalisation order, guard conditions — and are the parts that must be
   followed literally. Where a parameter is load-bearing (for example
   `sort_keys=True` in canonical serialisation, or `prev_hash` being inside the
   entry hash preimage), the document says so and says why.
4. Treat `registry/*.json` as the machine-readable mirror of the prose and
   `schemas/*.json` as the contract for every persisted structure. If prose and
   schema disagree, the schema is the narrower, safer reading.
5. Treat `evidence/*.json` as claims that were *executed*, not asserted. They can
   be regenerated and compared.
6. Never raise a status label during reconstruction. The ceilings in this package
   are deliberate: DNS stops at `LOCALLY_EXECUTED`, the production signer stops
   at `DEFINED`, and nothing anywhere reaches `PRODUCTION_VALIDATED`.

## 8. Licence and usage

See `LICENSE_OR_USAGE_NOTICE.md`.
