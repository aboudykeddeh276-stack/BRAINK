# IL-LLM Recursive Engineering Review — Pass 2

Status: REPLACEMENT CURRENT-STATE CORPUS FOR PASS 2
Input under attack: `ILLLM_PASS_1_CURRENT_STATE_R1.md`

## 1. Pass 2 governing posture
Pass 1 receives no inherited credibility. Its classifications, market statement, benchmark interpretation, and proposed recovery models are re-opened.

## 2. Pass 1 overstatement corrections
### 2.1 Atomicity was still framed too generously
Pass 1 called the file-replacement primitive `ATOMIC_FILE_REPLACEMENT_IMPLEMENTED`. That is syntactically accurate but semantically incomplete.

A better classification is:
`SAME-DIRECTORY CRASH-RESISTANT REPLACEMENT PRIMITIVE IMPLEMENTED`.

Reason:
- rename/replace atomicity addresses namespace visibility, not complete durable transaction semantics;
- fsync durability depends on host/filesystem behavior;
- permission/ownership semantics are not complete across all callers;
- VFS identity may span carrier + semantic index + proof + object metadata;
- compound logical mutations remain vulnerable to cross-object partial commit.

Therefore the market/architecture language must not use `atomic VFS` unless a transaction coordinator/WAL/manifest commit protocol spans the logical object family.

### 2.2 Projection rehydration is not one test
Pass 1 treated projection rehydration as one missing oracle. Pass 2 splits it into four independent recovery classes:

1. **Canonical object rehydration** — reconstruct runtime object from durable canonical carrier.
2. **Derived semantic-index rehydration** — rebuild sidecars/indices from canonical source.
3. **Observer projection regeneration** — rebuild observer/mirror-relative view without changing canonical identity.
4. **Runtime process rehydration** — restart supervised service and recover required state/continuation.

A system can pass one and fail another. Future reports must classify them separately.

### 2.3 Stale-lock recovery is broader than lock files
Pass 1's suggested lease/fence model is useful but overgeneralizes. The current ambiguity lives partly in the idempotency registry, which is command ownership/reconciliation state rather than merely a lock.

Pass 2 replaces `stale-lock recovery` with three separate protocols:
- ephemeral mutex recovery: OS/process lock disappears with process death;
- persistent ownership recovery: durable INFLIGHT/lease state must reconcile owner generation/liveness;
- participant mutation reconciliation: external effect may have happened even if local completion receipt did not.

A fencing token solves ownership races but does not prove whether a remote provider action already occurred. Participant readback or idempotent provider semantics are still required.

## 3. Benchmark attack
Pass 1 correctly noted statistical weaknesses but did not attack baseline construction strongly enough.

Current benchmark compares:
- a purposely whole-estate scan against a purpose-built term index;
- repeated linear definition scanning against a purpose-built definition index;
- complete synthetic runtime reconstruction against one-node registration.

Those are legitimate algorithmic contrasts but are **upper-bound demonstrations of avoidable work**, not fair representatives of all conventional systems.

A serious Pass 2 baseline suite must include:
1. optimized inverted-index retrieval;
2. graph-database indexed traversal;
3. cached Graph-RAG structural retrieval;
4. incremental materialized-view/dataflow baseline;
5. workbook-native recalculation/dependency baseline;
6. cold vs warm IL-LLM separately;
7. same-memory-budget comparison;
8. same-correctness/recall target.

The current `speedup` field must therefore be classified `ALGORITHMIC MICROBENCHMARK RATIO`, not market speedup.

## 4. Statistical experiment replacement requirements
Pass 2 replaces the prior experiment requirement with a stronger experimental protocol.

For each workload/size/configuration:
- >= 30 measured independent trials after warm-up where practical;
- raw samples persisted;
- median, mean, MAD/stddev, p50/p95/p99 where appropriate;
- bootstrap 95% CI for median ratio or speedup;
- randomized AB/BA execution ordering;
- host fingerprint: CPU, RAM, OS/kernel, Python/runtime versions, git SHA, thermal/power mode when observable;
- isolated cold-start series and warm-resident series;
- memory/RSS and index-size measurement;
- correctness oracle run for each sampled system, not just speed;
- scaling regression with R² and residual warning;
- explicit rejection of exponent interpretation when fit is poor.

Pass 2 classification of current benchmark: IMPLEMENTED REPEATED SYNTHETIC HARNESS; NOT YET SCIENTIFIC PERFORMANCE EVIDENCE.

## 5. Workbook advantage re-opened
Pass 1 called workbook-native computational knowledge a potential differentiator. Fresh research makes the premise strong but also weakens novelty claims.

Established spreadsheet research already treats spreadsheets as programming environments, including first-class functions/LAMBDA, typed values, higher-order functions, natural-language formula synthesis, and spreadsheet-grounded computation.

Therefore:
- `WORKBOOKS ARE COMPUTATIONAL CARRIERS` = established external fact, not Keddeh-specific novelty.
- Keddeh-specific differentiation, if proven, lies in **binding workbook computational structure into the same recursive IL-LLM/KEX identity, authority, runtime, observer, and proof graph**.

Novelty/market claims must target that integration rather than claiming discovery of spreadsheets-as-programs.

## 6. Incremental-computation claim re-opened
Differential dataflow establishes that incremental maintenance, including nested iterative computation, is a mature systems paradigm. Therefore IL-LLM delta updates are not novel merely because they avoid rebuilds.

Potential differentiation must instead be tested around:
- heterogeneous definition/workbook/code/service/proof graph integration;
- context-scoped traversal across those object classes;
- authority-aware executable lowering;
- observer/mirror projection maintenance;
- proof-preserving re-entry.

## 7. E-graph/equivalence claim re-opened
Equality saturation already provides compact representation of many equivalent forms and cost-based extraction. The IL-LLM equivalence layer should be classified as borrowing this family of mechanics unless it demonstrates materially different semantics.

Required future test:
- prove equivalence relation soundness under KEX/IL-LLM object semantics;
- bound saturation/extraction growth;
- verify observer-specific conditions do not merge globally incompatible states;
- report extraction cost and memory amplification.

## 8. Projection rehydration replacement test matrix
Future test harness MUST contain independent oracles:

| Recovery class | Destructive action | Required proof |
|---|---|---|
| canonical | stop runtime/delete volatile state | same canonical identity and content hash from durable source |
| semantic index | delete `.semantics.json`/index | regenerated graph semantically equivalent to source |
| observer projection | delete observer/mirror projection | regenerated view has correct context and no canonical mutation |
| runtime service | kill supervisor/child | new generation owns service, restores state, passes health/readback |
| stale projection | mutate canonical after projection | old projection rejected or marked stale |

## 9. VFS transaction architecture recommendation
Pass 2 rejects pretending multi-object VFS atomicity can be obtained by calling atomic rename several times.

Recommended design:
`intent/WAL -> stage immutable objects -> fsync -> write commit manifest/root -> fsync -> atomically advance canonical root pointer -> rebuild projections -> append proof/readback`.

The canonical root/manifest becomes the atomic publication point. Immutable staged objects that never become referenced are garbage-collectable.

This resembles content-addressed/MVCC/manifest-commit systems mechanically; it is not claimed equivalent to any one product.

## 10. Stale ownership/recovery recommendation
Recommended command state machine:

`NEW -> RESERVED(owner,generation,fence) -> EFFECT_UNKNOWN | EFFECT_CONFIRMED -> COMPLETED`

On restart:
1. detect old generation;
2. fence old owner;
3. query local/outbox/provider participant state;
4. if effect confirmed, reconstruct completion receipt;
5. if effect absent and retry is safe/idempotent, issue under new fence;
6. otherwise remain `AMBIGUOUS_MANUAL_OR_PARTICIPANT_RECONCILIATION_REQUIRED`.

This is stronger than merely expiring INFLIGHT by age.

## 11. Market statement replacement
Pass 1 market language was directionally reasonable but still too broad.

Pass 2 replacement:

**Keddeh Systems is building an experimental contextual execution substrate that attempts to unify recursive definitions, workbook computation, code/runtime objects, scoped authority, observer-relative projections, and proof/readback in one machine-traversable estate. Its differentiating value must be demonstrated in cross-domain resolution quality, incremental maintenance cost, authority safety, and recoverable execution, not inferred from indexing speed alone.**

## 12. Pass 2 replacement classifications
| Claim | Pass 2 current classification |
|---|---|
| same-directory fsync+replace primitive | IMPLEMENTED |
| logical multi-object VFS transaction | NOT IMPLEMENTED |
| canonical rehydration | NOT REPROVEN |
| semantic-index rehydration | NOT REPROVEN |
| observer projection rehydration | NOT REPROVEN |
| runtime-service rehydration | PARTIALLY IMPLEMENTED BY SUPERVISION; NOT CURRENTLY REPROVEN |
| persistent stale-owner recovery | NOT IMPLEMENTED |
| participant effect reconciliation | PARTIAL VIA OUTBOX/READBACK; INCOMPLETE |
| repeated timing harness | IMPLEMENTED |
| scientifically controlled benchmark | NOT IMPLEMENTED |
| workbook-as-computation premise | EXTERNALLY ESTABLISHED |
| workbook→IL-LLM integration | IMPLEMENTED SOURCE; EXECUTION NOT CURRENTLY REPROVEN |
| delta update advantage over full rebuild | MECHANISTICALLY EXPECTED; CURRENT MAGNITUDE UNVERIFIED |
| e-graph-like equivalence mechanics | IMPLEMENTED BORROWED PARADIGM; SOUNDNESS/SCALE NOT REPROVEN |
| market differentiation | HYPOTHESIS REQUIRING COMPARATIVE EVIDENCE |

## 13. Pass 3 attack queue
Pass 3 MUST attack Pass 2 on these grounds:
1. Does the proposed manifest/root VFS transaction model actually fit current KEX/VFS identity semantics, or is it imported orthodoxy?
2. Does splitting rehydration into four classes still miss reconstruction of cross-repository/global IL-LLM topology?
3. Is the statistical protocol itself appropriate for non-stationary resident systems, or do time-series/blocking effects require a different design?
4. Does Pass 2 understate the architectural value of workbook integration by over-correcting against novelty?
5. Is `authority-aware executable lowering` actually enforced end-to-end or merely present in translator source?
6. Does the market statement still depend on unmeasured integration benefits?
7. Which Pass 2 recommendations increase complexity enough to damage the very acceleration phenomenon being studied?
