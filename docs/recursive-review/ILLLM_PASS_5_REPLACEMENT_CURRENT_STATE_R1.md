# IL-LLM Recursive Engineering Review — Pass 5

Status: REPLACEMENT CURRENT-STATE CORPUS FOR PASS 5
Governing law: `docs/ILLLM_RECURSIVE_REVIEW_CONTRACT_R1.md`
Required input under attack: `docs/recursive-review/ILLLM_PASS_3_REPLACEMENT_CURRENT_STATE_R1.md`
Post-Pass-3 branch artifacts treated as untrusted evidence: Pass 4 report, continuation record, oracle-projection mutation/test, workflow changes, and all current source.

## 1. Pass 5 posture
Pass 3 was not accepted as validated. Pass 4 was not accepted as validated merely because it is newer. Both were re-opened against current source and fresh workflow evidence.

The current PR is open, unmerged and mergeable. The branch advanced beyond the Pass 3 head and therefore contains an actionable state change.

## 2. Fresh workflow evidence
Head `05890341d0e68ed46d5fee8bf607c5b0040b50db` produced:
- KEX Runtime Hardening run `33558330435`, run #105: `completed/failure`; job `100024528731` exposes no executed steps.
- Casepath Management Validation run `33558330479`, run #107: `completed/failure`.

Pass 5 classification: the hardening run remains a PRE-STEP / EXECUTOR-BOUNDARY failure, not a code/test failure receipt. Repeating the same zero-step failure does not justify another unchanged CI retry as engineering progress.

## 3. Pass 3 stale-owner claim attacked and materially advanced
Pass 3 classified duplicate suppression as implemented but stale-owner/effect recovery as incomplete. Current `idempotency.py` still retains INFLIGHT reservations and does not itself provide lease expiry, owner generations or fencing.

Pass 5 adds `modules/kex_wbos/lease_fencing.py`, a persistent local ownership primitive with:
- resource identity;
- owner identity;
- acquisition generation;
- monotonic fencing token;
- acquisition/heartbeat/expiry timestamps;
- live-lease refusal;
- stale-lease takeover with monotonically newer fence;
- `validate_fence()` for resource-side stale-owner rejection;
- effect states including `EFFECT_AMBIGUOUS` and `MANUAL_RECONCILIATION`;
- preservation of ambiguous effect state across ownership takeover;
- refusal to let a fenced predecessor publish a later effect transition.

Pass 5 also adds `scripts/kex-ci/test_lease_fencing.py`. The hostile test requires:
1. owner A acquires fence 1;
2. owner B cannot steal a live lease;
3. owner A renews the lease;
4. owner B can take over only after expiry and receives fence 2;
5. resumed owner A is rejected as `FENCED`;
6. owner B can publish effect state;
7. fence generations remain monotonic after release/reacquire;
8. `EFFECT_AMBIGUOUS` survives takeover for reconciliation;
9. an old owner cannot publish `COMPLETED` after a newer fence exists.

The KEX Runtime Hardening workflow now compiles and runs this regression when an executor actually starts configured steps.

### Reclassification
- duplicate suppression: IMPLEMENTED SOURCE;
- local lease/fence registry: IMPLEMENTED SOURCE IN PASS 5;
- stale-owner rejection oracle: IMPLEMENTED TEST SOURCE, EXECUTION PENDING;
- governed-resource integration of `validate_fence()`: NOT YET COMPLETE;
- external participant effect reconciliation: PARTIAL / PARTICIPANT-DEPENDENT;
- full stale-owner/effect recovery: NOT YET VERIFIED.

This is deliberately narrower than calling stale-owner recovery complete. A fencing token only protects a resource that actually checks it.

## 4. Projection rehydration attack
Pass 4's retained `lastOracle` change is still only source-level projection continuity. It does not satisfy destructive rehydration across Pass 3's eight classes.

Current classification:
1. canonical carrier rehydration — NOT CURRENTLY REPROVEN;
2. semantic-index rehydration — NOT CURRENTLY REPROVEN;
3. observer/mirror regeneration — NOT CURRENTLY REPROVEN;
4. runtime-process/service rehydration — PARTIAL SUPERVISION SOURCE;
5. global IL-LLM topology rehydration — NOT CURRENTLY REPROVEN;
6. definition-lineage rehydration — NOT CURRENTLY REPROVEN;
7. authority/capability rehydration — NOT CURRENTLY REPROVEN;
8. proof-lineage projection retention — IMPLEMENTED SOURCE IMPROVEMENT, DESTRUCTIVE PROOF PENDING.

Pass 5 rejects any claim that oracle retention equals rehydration verification.

## 5. Atomic VFS / compound-write attack
The current `hardening.py` single-carrier primitive remains defensible as source implementation: sibling temporary file, flush/fsync, `os.replace`, and containing-directory fsync.

Pass 5 does not promote that primitive to compound VFS atomicity.

Still missing:
- immutable or otherwise isolated candidate generation;
- explicit commit descriptor binding logical identity, generation, member hashes, semantic graph root and proof root;
- one canonical generation switch;
- recovery discrimination between old committed, new committed and incomplete candidate states;
- derived-sidecar/projection invalidation bound to the committed generation;
- destructive crash/fault oracle.

Classification remains:
- single-carrier local replacement primitive: IMPLEMENTED SOURCE;
- compound local KEX/VFS generation commit: NOT IMPLEMENTED;
- cross-provider atomic transaction: REJECTED AS CURRENT CLAIM;
- outbox/saga/reconciliation boundary for external participants: ARCHITECTURALLY APPROPRIATE, EXECUTION-SPECIFIC PROOF REQUIRED.

## 6. Repeated statistical experiment attack
Current benchmark source still performs repeated measurements, medians/p95 and scaling fits, but it does not yet meet the recursive review contract's controlled-experiment gate.

Pass 5 current deficiencies:
- raw trial distributions are not persisted as the primary evidence artifact;
- baseline/candidate order is not randomized or counterbalanced;
- no bootstrap effect-size interval is emitted;
- no serial-dependence or blocked-batch analysis exists;
- no competent indexed/materialized external baseline is measured;
- memory/index amplification is not part of the result;
- fitted exponents remain descriptive regime fits, not complexity proofs.

Classification:
- repeated synthetic timing: IMPLEMENTED SOURCE;
- controlled statistical experiment suite: NOT IMPLEMENTED;
- universal acceleration: REJECTED;
- workload-bounded semantic-work reduction: PLAUSIBLE EXPERIMENTAL HYPOTHESIS.

## 7. Fresh external paradigm check
Current distributed-lock guidance continues to distinguish safety from liveness and documents failure modes where crash/failover can permit conflicting ownership. Pass 5 therefore preserves the design rule that lease expiry alone cannot be treated as proof that a prior owner/effect is harmless. The new local primitive adds monotonic fences, but external resources still need participant-side idempotency/readback or explicit ambiguity handling.

No novelty claim is assigned to leases, fencing, idempotency, atomic rename, incremental computation, indexes or spreadsheet programmability. The KEX/IL-LLM research hypothesis remains their integration under stable logical identity, recursive definitions, heterogeneous carriers, contextual traversal, scoped execution, observer projections and proof/re-entry.

## 8. Current claim ledger
| Claim | Pass 5 classification |
|---|---|
| Recursive IL-LLM definition/context substrate | IMPLEMENTED SOURCE |
| Workbook semantic carrier analysis | IMPLEMENTED SOURCE |
| Intent-to-capability translation | IMPLEMENTED SOURCE; end-to-end authorization proof pending |
| Resident latest-oracle projection retention | IMPLEMENTED SOURCE; execution pending |
| Single-carrier atomic replacement | IMPLEMENTED SOURCE |
| Compound KEX/VFS generation commit | NOT IMPLEMENTED |
| Destructive eight-class rehydration suite | NOT IMPLEMENTED |
| Local lease/fence primitive | IMPLEMENTED SOURCE IN PASS 5 |
| Fenced predecessor rejection test | IMPLEMENTED TEST SOURCE; EXECUTION PENDING |
| Governed mutation resource-side fence enforcement | NOT YET INTEGRATED COMPLETELY |
| External effect reconciliation | PARTIAL / PARTICIPANT-DEPENDENT |
| Repeated synthetic benchmark | IMPLEMENTED SOURCE |
| Controlled statistical experiment suite | NOT IMPLEMENTED |
| Current GitHub hardening execution | PRE-STEP EXECUTOR BOUNDARY |
| TL2_LIVE | NOT PROMOTED |
| PUBLIC_LIVE | NOT PROMOTED |
| Universal IL-LLM speedup | REJECTED |
| Workload-bounded semantic-work reduction | PLAUSIBLE HYPOTHESIS |

## 9. Material Pass 5 mutations
- `4788d954423c25bd38377820261aab99f441a778` — add `modules/kex_wbos/lease_fencing.py`.
- `673106630ba14432bdf698d305cc3278acffec2f` — add hostile stale-owner/effect-ambiguity regression.
- `5db8692a6996076804c48f22a2ec1ee6e53dbc13` — gate the regression in KEX Runtime Hardening CI.

## 10. Next proof sequence
1. observe whether any configured step executes on a current-head workflow run; do not classify zero-step failure as code failure;
2. execute `test_lease_fencing.py` on branch-equivalent bytes and capture the receipt;
3. integrate `validate_fence()` immediately before at least one governed canonical local mutation, then prove a stale predecessor cannot publish;
4. implement compound local KEX/VFS generation commit plus crash-recovery oracle;
5. implement destructive rehydration experiments across all eight classes;
6. upgrade the benchmark to raw-sample controlled experiments with stronger baselines and uncertainty analysis;
7. run the next recursive pass against this entire report as hostile current input.

## 11. Supersession rule
This file is the replacement interpretation emitted from the current branch evidence. Passes 1–4 remain lineage only. Nothing here receives inherited validation in the next pass.
