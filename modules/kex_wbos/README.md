# KEX/WBOS + Recursive IL-LLM Runtime

This directory is the resident Python control/runtime layer for KEX, WBOS, Casepath integration, workbook semantics, TL2 service operation and IL-LLM.

## Runtime responsibilities

The directory is intentionally split by responsibility so local correctness does not bypass global invariants.

| Module | Responsibility | Evidence/claim boundary |
|---|---|---|
| `action_server.py` | HTTP action façade and route dispatch | Route presence is not actuator success |
| `action_runtime.py` | Typed action execution, receipts, readback and action ledger | Receipt status must match observed state |
| `action_extensions.py` | Workbook append and BrainK migration-manifest actions | Migration manifest is not semantic ingestion |
| `capabilities.py` | Signed action/target-scoped capabilities | Not a complete object-capability OS |
| `idempotency.py` | Duplicate suppression/replay state | Not distributed exactly-once semantics |
| `object_store.py` | SHA-256 content-addressed object identity and provenance | Content addressing is not physical storage replacement |
| `outbox.py` | Durable external-action intent and reconciliation | `PENDING` is intent, not external execution |
| `hardening.py` | Canonical JSON, atomic/fsync writes, locks, containment helpers | Local primitives still require caller-level invariants |
| `network_policy.py` | Readback/credential destination policy | Network authorization is explicit per destination |
| `service_supervisor.py` | WBOS worker lifecycle, generation and restart history | `RUNNING` requires current generation identity |
| `resident_runtime_controller.py` | Resident BRAINK service health/recovery/oracles | GitHub CI is optional observation, not host liveness |
| `capability_fabric.py` | Integrated local capability exercise + TL2 participant boundary | Local verification is not TL2 or public promotion |
| `casepath_management.py` | Managed Casepath process dispatch and accountability | Process registration is not public-site publication |
| `workbook_api.py` | Workbook discovery/data surfaces and activation | Parsed rows are not formula/macro execution |
| `workbook_semantics.py` | Formula/dependency graph, ranges, SCC/cycle analysis | Static dependency graph is not workbook execution |
| `server.py` | WBOS cascade/data API surface | Local server is not production ingress |

## IL-LLM module family

IL-LLM is not one class. The runtime separates primary structure, traversal, translation and optimisation.

### Primary definition substrate

`illlm_definitions.py` makes definitions first-class addressable objects. A definition may itself be the subject of another definition. Primary relations include:

```text
DEFINITION_OF
SPECIALISES
GENERALISES
LOWERS_TO
EXECUTES_AS
OBSERVED_AS
PROVEN_BY
```

Memory and conversational context are deliberately absent from this primary graph. They are secondary state/navigation layers.

### Recursive topology

`illlm_recursive_runtime.py` implements:

- acyclic containment/ancestry;
- cyclic traversal relations;
- contextual candidate indices;
- execution-route indices;
- context frames and re-entry;
- costed graph traversal;
- deterministic graph hashes.

`illlm_higher_order.py` materialises the historical IL-LLM-of-IL-LLMs topology. `illlm_hydrator.py` converts that persisted topology and cross-repository carriers into the live recursive runtime.

### Context/security translation

`illlm_context_gateway.py` and `illlm_context_translator.py` interpose IL-LLM between intent and capability. The intended security flow is:

```text
local IL-LLM intent
→ enter global IL-LLM through declared context
→ resolve resident semantic/execution object
→ compile ACTION::TARGET
→ mint narrow capability
→ downstream actuator
→ receipt
→ context re-entry
```

The translator does not treat prose as an actuator command and does not treat successful translation as successful execution.

### Incremental semantic processing

`illlm_delta_engine.py` retains facts and propagates only new deltas through registered rules. This is the resident alternative to rebuilding the entire semantic estate for each local change.

The engineering donor is semi-naive/differential evaluation: reuse previous results and process changed facts. This is an algorithmic similarity, not a claim that this module is Differential Dataflow.

### Equivalence and route extraction

`illlm_equivalence.py` preserves multiple equivalent forms with explicit cost/proof/execution metadata and extracts an allowed low-cost form deterministically. This borrows the useful non-destructive idea from equality-saturation/e-graph systems while retaining KEX-specific proof boundaries.

### Executable graph

`illlm_executable_graph.py` represents objects that can simultaneously carry semantic terms, mathematical state, knowledge edges, execution edges, state-transition edges, proof edges and source/carrier identity.

### Resident service

`illlm_service.py` exposes the live IL-LLM service. Default loopback port: `8791`.

Current routes:

```text
GET  /health
GET  /snapshot
POST /query
POST /traverse
POST /translate
POST /delta
POST /facts/delta
POST /facts/query
POST /equivalence/register
POST /equivalence/extract
POST /rebuild
```

`illlm_service_supervisor.py` owns the service lifecycle. Non-loopback binding requires the runtime authentication policy.

## Sector/context roots

The global topology is intended to treat KEX Seed, KEX DNA, VFS, quantum-computing, observer and Mirror Lane artifacts as typed entry contexts into the same substrate, not as unrelated slogans. Cross-repository carriers preserve source repository/revision evidence.

## Demonstration

From the repository root:

```bash
python3 scripts/kex-ci/demo_massive_illlm.py
```

The demo should show:

1. definition-of-definition traversal;
2. contextual query against a resident global frame;
3. typed intent-to-capability translation;
4. delta fact propagation without full rebuild;
5. equivalence registration and deterministic extraction;
6. proof/graph hashes for reproducibility.

For scaling measurement:

```bash
python3 scripts/kex-ci/benchmark_illlm_phenomenon.py --sizes 1000,5000,10000 --repeats 100
```

## Architectural invariants

- Definition identity is primary; memory/context cannot silently redefine it.
- A local IL-LLM may only operate through the global context/scope it entered.
- Translation and execution are separate proof stages.
- Containment remains acyclic; traversal may be cyclic and re-entrant.
- External intent must remain pending until participant evidence arrives.
- Service promotion must identify the current supervised generation.
- Proof/readback state cannot be substituted by source presence, CI configuration or UI projection.

## Market relevance

The unusual market proposition of this module family is not “another chatbot.” The technically testable proposition is a resident contextual execution substrate in which definitions, semantic relations, code routes, current state, authority and proof can remain linked as machine objects. If real-estate benchmarks show lower scaling exponents and lower reconstruction work than repeated retrieval/reinterpretation, this could matter to agent runtimes, operational decision systems, regulated workflows, digital engineering, domain-specific automation and persistent enterprise knowledge systems.

Those are market hypotheses until benchmarked on real workloads. See `docs/ILLLM_CAPABILITY_MARKET_IMPACT_LEDGER_R1.md` for claim classification.
