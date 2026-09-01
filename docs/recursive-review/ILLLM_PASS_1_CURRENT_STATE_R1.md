# IL-LLM Recursive Engineering Review — Pass 1

Status: REPLACEMENT CURRENT-STATE CORPUS FOR PASS 1
Branch reviewed: `kex-runtime-hardening-r3`
Review contract: `docs/ILLLM_RECURSIVE_REVIEW_CONTRACT_R1.md`

## 1. Method
Pass 1 treats the current repository, current PR claims, current documentation, current tests, and fresh external research as untrusted source material. Historical statements are lineage only.

Evidence classes: IMPLEMENTED, EXECUTED, VERIFIED, INFERRED, HYPOTHESIS, STALE, REJECTED.

Fresh external mechanisms reviewed:
- Differential dataflow / incremental iterative computation: reuse prior results under changing inputs; relevant to IL-LLM delta propagation.
- Equality saturation / e-graphs: preserve alternative equivalent forms and extract by cost; relevant to contextual representation/executable lowering.
- POSIX fsync/rename durability discipline: relevant to VFS-backed atomic canonical mutation.
- Systems benchmarking reproducibility research: repeated runs and variability are mandatory for performance claims.

Paradigm similarity is not equivalence.

## 2. Current architectural determination
The strongest defensible description of the current IL-LLM estate is:

`machine-addressable definitions + higher-order definition relations + contextual graph traversal + workbook semantic carriers + scoped action translation + incremental graph/fact updates + proof-bearing resident services`.

This is materially stronger than RAG-like document retrieval, but current evidence does NOT yet establish universal semantic acceleration, autonomous intelligence, or general market performance.

## 3. Projection rehydration
Classification: HYPOTHESIS / PARTIALLY IMPLEMENTED INFRASTRUCTURE, NOT VERIFIED.

Observed supporting pieces:
- canonical/runtime state is persisted independently of user-facing projections;
- workbook semantics are emitted as sidecar graph state;
- resident controller can reconstruct service state from persisted supervisor files;
- IL-LLM graph hydration/rebuild routes exist elsewhere in the branch.

Missing proof:
- no dedicated destructive rehydration oracle was observed that deletes a derived projection/cache, reconstructs it from canonical VFS/source state, and checks identity, provenance, graph hash, observer-relative state, and absence of projection-to-canonical privilege escalation;
- no repeated clean-start projection rehydration experiment is currently part of the benchmark suite.

Pass 1 determination: do not call projection rehydration VERIFIED.

Required implementation/test:
1. materialize canonical fixture;
2. generate projection and record canonical/projection hashes;
3. delete derived projection/cache;
4. restart/hydrate from canonical state;
5. regenerate projection;
6. assert stable canonical identity and semantic equivalence;
7. assert stale projection is rejected after canonical mutation;
8. repeat across observer/mirror contexts.

## 4. Atomic VFS writes
Classification: IMPLEMENTED FOR CORE FILE REPLACEMENT PRIMITIVE; NOT YET VERIFIED AS A COMPLETE VFS TRANSACTION MODEL.

`hardening.atomic_write_bytes` performs sibling temporary-file creation, write, flush, file fsync, atomic replace, directory fsync where supported, and optional mode preservation.

Strengths:
- avoids ordinary torn canonical-file replacement;
- preserves same-directory rename atomicity assumptions;
- acknowledges platform/substrate limitations;
- creates a reusable primitive for state files and reports.

Remaining defects/limits:
- fsync semantics remain filesystem/platform dependent;
- ownership preservation is not generalized;
- multi-object mutations (workbook + semantic sidecar + proof record) are not one atomic transaction;
- append-only ledgers use direct O_APPEND + fsync rather than a transaction log/indexed tail protocol;
- proof should not promote a compound mutation until all dependent carriers are reconciled.

Pass 1 determination: `ATOMIC_FILE_REPLACEMENT_IMPLEMENTED`; `ATOMIC_VFS_TRANSACTION_VERIFIED` is rejected.

## 5. Stale-lock recovery
Classification: NOT IMPLEMENTED as a complete recovery protocol.

The idempotency registry has process-local locking plus fcntl advisory locking where available. INFLIGHT reservations are retained and never silently compacted, which is safer than blindly replaying ambiguous mutation.

However, persistent INFLIGHT state contains request hash and reservation time but no:
- owner PID/process identity;
- boot/session generation;
- lease expiry;
- heartbeat;
- fencing token;
- participant reconciliation result;
- takeover/recovery event.

Therefore crash ambiguity is blocked but not recovered.

Pass 1 determination: `DUPLICATE_SUPPRESSION_IMPLEMENTED`; `STALE_LOCK_RECOVERY` and `EXACTLY_ONCE` are REJECTED.

Required design:
`reservation = {ownerId, generation, fence, reservedAt, heartbeatAt, requestHash}`
with recovery requiring owner-liveness or lease evidence, participant reconciliation, monotonic fencing, and append-only recovery proof.

## 6. Repeated statistical experiments
Classification: IMPLEMENTED AT BASIC REPEAT LEVEL; SCIENTIFICALLY INCOMPLETE.

Current benchmark performs repeated timings, reports median and p95, tests multiple estate sizes, and estimates log-log scaling exponents.

This is a meaningful improvement over one-shot benchmarking.

Missing experimental controls:
- raw trial observations are not persisted;
- mean and dispersion are not reported;
- confidence/Bootstrap intervals are absent;
- baseline vs indexed order is not randomized/counterbalanced;
- host/runtime build/configuration fingerprint is incomplete;
- no goodness-of-fit/R² or residual analysis accompanies scaling exponents;
- cold-build, warm lookup, delta, and translation share one process and may interact through cache/thermal/allocator effects;
- synthetic workload does not establish real-estate or market performance.

Pass 1 determination: current benchmark can support `SYNTHETIC REPEATED MICROBENCHMARK` claims only.

## 7. IL-LLM computational phenomenon
Classification: STRUCTURALLY SUPPORTED HYPOTHESIS.

The architecture can reduce repeated semantic work when:
- the definition/relationship estate is already resident;
- contextual selectivity is high;
- relevant indices remain bounded;
- update closure is small relative to the estate;
- graph maintenance cost does not dominate query savings.

The correct measurement family is not a single speedup ratio but:
- work avoided;
- query latency distribution;
- update latency distribution;
- memory amplification;
- index maintenance cost;
- rehydration cost;
- scaling exponent with model fit;
- semantic correctness/recall of the selected context;
- executable-lowering correctness.

## 8. Market-impact determination
Current defensible market position:

**A contextual executable knowledge/runtime substrate that preserves definitions, code, workbook computation, state, authority, and proof as linked machine objects.**

Potential differentiators:
- workbook-native computational knowledge rather than flattened documents;
- recursive definition-of-definition navigation;
- contextual local-IL-LLM entry into a global estate;
- action authority derived through translation rather than ambient agent authority;
- incremental semantic maintenance;
- proof/readback and observer/mirror lineage.

Not yet defensible:
- universal orders-of-magnitude end-to-end AI acceleration;
- general superiority to vector databases/Graph-RAG/LLMs across arbitrary workloads;
- production-resilient stale-lock recovery;
- complete crash-consistent multi-object VFS transaction semantics;
- experimentally verified projection rehydration.

## 9. Active defects affecting promotion
Current review surface still contains live concerns including:
- bearer credential leakage risk on generic HTTP readback targets;
- workbook sidecar freshness after mutation;
- scoped capability forwarding through facade routes;
- stale/escaped workbook and migration paths;
- ledger append O(history) tail discovery;
- controller latest-oracle state retention;
- checkpoint identity under same-length divergent histories.

A mergeable PR is not equivalent to resolved engineering acceptance.

## 10. Pass 1 replacement classifications
| Claim | Pass 1 classification |
|---|---|
| Recursive definition graph | IMPLEMENTED |
| Contextual IL-LLM traversal | IMPLEMENTED |
| Intent → scoped capability translation | IMPLEMENTED |
| Workbook → IL-LLM semantic carrier | IMPLEMENTED |
| Incremental/delta mechanisms | IMPLEMENTED, EXECUTION NOT CURRENTLY REPROVEN |
| Atomic file replacement | IMPLEMENTED |
| Atomic multi-object VFS transaction | NOT VERIFIED |
| Projection rehydration | NOT VERIFIED |
| Stale-lock recovery | NOT IMPLEMENTED |
| Repeated benchmark trials | IMPLEMENTED |
| Statistically rigorous performance experiment | NOT YET IMPLEMENTED |
| Phenomenal semantic-work reduction | HYPOTHESIS WITH MECHANISTIC BASIS |
| Universal speedup | REJECTED |
| Market differentiation | INFERRED, REQUIRES FRESH COMPETITIVE BENCHMARKING |

## 11. Pass 2 attack queue
Pass 2 MUST attack this report itself, specifically:
1. challenge whether Pass 1 overstates atomicity merely because `fsync + replace` exists;
2. challenge whether projection rehydration is actually one concept or multiple independent state-restoration problems;
3. challenge whether stale locks should be modeled as leases, ownership generations, or participant-reconciliation state rather than a generic lock problem;
4. challenge the benchmark baseline for fairness and asymptotic interpretation;
5. challenge the market statement against current graph databases, dataflow engines, spreadsheet systems, compiler IRs, and agent runtime products;
6. re-open every Pass 1 classification rather than citing this report as validated.
