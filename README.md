# BRAINK / KEX / IL-LLM

BRAINK is the active Keddeh Systems repository for the resident KEX/WBOS runtime, recursive IL-LLM traversal, workbook-backed data/semantic services, capability-scoped action execution, proof/readback, TL2 deployment, and native application integration.

This repository must be read as a software system, not as a collection of disconnected demonstrations. The governing execution boundary is:

```text
source / definition / workbook / runtime object
→ machine identity
→ contextual traversal
→ typed action or service route
→ execution
→ readback
→ proof
→ continuation
```

## Current architecture

### KEX/WBOS resident runtime

`modules/kex_wbos/` contains the Python resident control and service layer. It includes action execution, scoped capabilities, idempotency, content-addressed objects, workbook adapters, proof/readback, supervision, TL2 deployment support, Casepath management, durable outbox processing, and the recursive IL-LLM service.

### IL-LLM

IL-LLM is implemented as a recursive machine-traversable knowledge/execution substrate rather than a single retrieval helper. The current branch includes:

- recursive IL-LLM nodes and traversal edges;
- acyclic containment plus cyclic/re-entrant traversal;
- higher-order IL-LLM topology and cross-repository carriers;
- first-class definitions and definitions-of-definitions;
- contextual intent-to-capability translation;
- semi-naive/delta fact evaluation;
- equivalence classes and deterministic cost extraction;
- executable graph edges;
- resident HTTP service and supervisor;
- performance/scaling benchmarks.

Context and memory are secondary layers over the primary identity/definition/relation/execution substrate.

### Workbook substrate

Workbook services parse resident `.xlsx`/`.xlsm` carriers, expose named data surfaces, generate formula dependency graphs, detect dependency cycles, and write semantic sidecars. Static workbook analysis does not by itself execute Excel formulas, macros, external links, or host automation.

### Resident service hierarchy

```text
K-Cloud / server substrate lineage
→ resident BRAINK controller
   ├─ WBOS action-service supervisor
   └─ IL-LLM recursive-runtime supervisor
→ service health/readback
→ proof / recovery / continuation
```

GitHub is source control and an optional external qualification surface. Runtime liveness must not depend on GitHub Actions.

### TL2 deployment

TL2 is a private/tunnel deployment class. `TL2_LIVE` requires the newly launched supervised service generation to be running and to pass inside-tunnel readback. It does not imply `PUBLIC_LIVE`, public DNS, public TLS, or public website publication.

## Major sections

| Section | Purpose |
|---|---|
| `modules/kex_wbos/` | Resident KEX/WBOS/IL-LLM runtime and security/control primitives |
| `NativeChatBot/` | Native Swift client/runtime integration |
| `runtime/` | Resident state, bindings, VFS/service-state contracts, checkpoints and continuation state |
| `deploy/` | Deployment actuators, especially TL2 |
| `openapi/` | API contracts and external interface descriptions |
| `scripts/kex-ci/` | Hostile tests, demonstrations, benchmarks and verification tools; not the runtime host |
| `docs/` | Case studies, architecture determinations, evidence and market-impact analysis |
| `.kex/` | Engineering/governance standards and control-plane configuration |

## Demonstrating IL-LLM

The branch contains two complementary demonstrations:

```bash
python3 scripts/kex-ci/demo_massive_illlm.py
python3 scripts/kex-ci/benchmark_illlm_phenomenon.py --sizes 1000,5000,10000 --repeats 100
```

The demo exercises definition recursion, contextual traversal, delta facts, equivalence extraction and intent-to-capability translation. The benchmark separates contextual-index acceleration, definition-chain acceleration, incremental-maintenance acceleration and translation overhead.

Synthetic benchmark output is not a resident-host market-performance claim. Promotion requires repeatable measurements against the real Keddeh Systems estate and target runtime.

## Claim discipline

The repository uses the following evidence classes:

- **SOURCE_RESIDENT**: implementation exists in the repository.
- **STRUCTURALLY_VERIFIED**: static/readback evidence confirms the declared structure.
- **LOCAL_EXECUTED**: an executable path has produced a local receipt.
- **TL2_LIVE**: the current supervised service generation is live through TL2 and passes tunnel readback.
- **PUBLIC_LIVE**: separate public DNS/TLS/ingress/outside-in evidence exists.
- **BENCHMARKED**: measurements exist for the exact implementation/environment claimed.
- **EXTERNALLY_VALIDATED**: an independent external authority or replicator has validated the stated claim.

No later state should be inferred from an earlier one.

## Research basis used as engineering donors

The system borrows mechanisms, not prestige, from established computer-science paradigms:

- incremental/differential computation for delta updates;
- Rete-style retained partial matching for repeated relational work;
- e-graph/equality-saturation ideas for preserving alternative representations and extracting low-cost valid forms;
- capability/reference-monitor and LangSec principles for narrowing intent before actuator execution;
- event sourcing/hash-linked receipts for replayable state evidence;
- content addressing for immutable object identity;
- supervisor/worker separation for resident lifecycle recovery;
- digital-twin concepts as a comparison point for observer-relative digital representations, without equating repository-local models with a validated real-world twin.

Each imported paradigm is documented with its invalid promotions: similarity does not prove equivalence.

## Documentation

Start with:

- `modules/kex_wbos/README.md`
- `runtime/README.md`
- `deploy/README.md`
- `scripts/kex-ci/README.md`
- `openapi/README.md`
- `docs/README.md`
- `docs/ILLLM_CAPABILITY_MARKET_IMPACT_LEDGER_R1.md`

## Active integration state

The active hardening/integration work is tracked in PR #58 on branch `kex-runtime-hardening-r3`. The branch contains substantial resident-runtime and IL-LLM implementation, but it must still be promoted only through available execution evidence and unresolved review defects must remain visible until repaired and re-read back.
