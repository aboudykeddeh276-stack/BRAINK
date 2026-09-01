# KEX Capability Fabric Case Study R1

## Objective

Exercise the strongest currently resident KEX/BRAINK mechanics as one coordinated software path rather than as isolated demonstrations.

## Starting claim

The system contains useful primitives for governed mutation, evidence, workbook semantics, content identity, lifecycle management and private deployment. The claim under test is not that these primitives form a completed distributed operating system. The narrower claim is that they can be composed into a coherent local capability fabric with explicit external-action boundaries.

## Mechanics invoked

1. Scoped signed capability credentials constrain action class and target prefix.
2. Persistent idempotency keys suppress same-intent duplicate local mutation and detect conflicting key reuse.
3. Source ingest creates both a filesystem carrier and a SHA-256 content-addressed object identity.
4. Casepath dispatch resolves through the dynamic management process ledger and emits a managed dispatch receipt.
5. A generated workbook is analysed as a dependency graph, including strongly connected cycle detection.
6. External TL2 intent is durably staged into an outbox rather than falsely marked executed.
7. A proof event reconciles source, dispatch, workbook graph and outbox state.
8. The chained action-ledger head is exported as a retained checkpoint.
9. When explicitly invoked on a TL2-capable host, the same harness can call the real TL2 deployer and reconcile its participant receipt.

## Systems-engineering paradigms exploited

### Capability security

Transferred mechanic: authority is constrained by action and target scope, not merely identity authentication.

Boundary: the implementation is a signed scoped credential mechanism, not a complete object-capability operating system.

### Idempotent command processing

Transferred mechanic: retries use a durable command identity. Same request + same key replays the original receipt; different request + same key is rejected.

Boundary: this is not distributed exactly-once execution.

### Content-addressed storage / Merkle-style identity

Transferred mechanic: immutable object identity derives from content hash while filesystem paths remain carriers.

Boundary: a single SHA-256 object store is not a complete Merkle DAG or distributed storage system.

### Spreadsheet programming / dependency analysis

Transferred mechanic: workbook formulas are treated as program dependencies and compiled into a semantic graph with SCC/cycle analysis.

Boundary: static graph extraction does not execute formulas, macros, volatile functions or external links.

### Transactional outbox

Transferred mechanic: external actuator intent is persisted before delivery, keeping local commit state separate from external participant execution.

Boundary: the current outbox is a durable relay contract. It does not itself make an external participant transactional.

### Saga/orchestration thinking

Transferred mechanic: multi-step work is represented as locally provable stages with explicit unresolved external participants instead of pretending one ACID transaction spans unrelated systems.

Boundary: compensating actions must be designed per real external participant before a full saga guarantee can be claimed.

### Event sourcing / retained proof head

Transferred mechanic: ordered receipts are replay-checked and the current ledger head can be retained separately as a rollback/truncation comparison point.

Boundary: a checkpoint stored beside the ledger does not protect against destruction of both; independent persistence remains required for stronger tamper evidence.

## Integrated exercise path

```text
scoped capability
→ idempotent SOURCE_INGEST
→ content-addressed object + carrier
→ exact receipt replay
→ managed CASEPATH_DISPATCH
→ workbook semantic graph + cycle oracle
→ durable TL2 outbox intent
→ proof-ledger mutation
→ chained ledger checkpoint
→ optional TL2 participant execution/readback
→ reconciled capability report
```

## Material implementation

- `modules/kex_wbos/capability_fabric.py`
- `modules/kex_wbos/outbox.py`
- `modules/kex_wbos/ledger_checkpoint.py`
- `scripts/kex-ci/exercise_capability_fabric.py`
- `.github/workflows/kex-runtime-hardening.yml`

## Acceptance oracles

The local capability fabric is verified only if all of the following hold in one execution:

- source mutation receipt is `MUTATED`;
- retry with the same idempotency key returns the exact original receipt hash;
- managed Casepath dispatch is `MUTATED`;
- content-addressed object ID is present;
- workbook graph hash is produced;
- intentional workbook cycle is detected;
- external TL2 intent is durably `PENDING` or `DELIVERED`;
- proof event is written;
- ledger-head checkpoint is materialised.

`TL2_LIVE` remains separate and requires the actual tunnel deployer to return a successful participant receipt.

## Current execution state

At the time this case study was committed, GitHub Actions run #24 for `KEX Runtime Hardening` was queued for the capability-fabric head. Therefore the integrated harness is resident but no hosted execution pass is claimed yet.

## Determination

The useful engineering move is to compose KEX primitives into explicit command/evidence boundaries rather than increasing vocabulary. The capability fabric now has a concrete execution contract. Its next promotion depends on an actual executor running the harness and, separately, a real TL2 host if private deployment is to be promoted to `TL2_LIVE`.
