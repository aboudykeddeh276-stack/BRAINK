# IL-LLM Recursive Engineering Review — Pass 4

Status: REPLACEMENT CURRENT-STATE CORPUS FOR PASS 4
Input under attack: `docs/recursive-review/ILLLM_PASS_3_REPLACEMENT_CURRENT_STATE_R1.md`
Governing law: `docs/ILLLM_RECURSIVE_REVIEW_CONTRACT_R1.md`

## 1. Pass 4 posture
Pass 3 is historical evidence, not authority. Every surviving classification was reopened against the current branch, fresh workflow evidence, current source, and current external systems literature.

## 2. Actionable delta since Pass 3
PR #58 remains open, unmerged, and currently mergeable. Head `90005b2434064b10ffb7d0c494a3078938addd56` produced fresh GitHub Actions runs:

- KEX Runtime Hardening run `33557360294`, run #100: `completed/failure`; job `100021339391` exposes zero steps.
- Casepath Management Validation run `33557360308`, run #102: `completed/failure`; its sole job likewise exposes no executable steps.

Pass 4 classification: these are **PRE-STEP / EXECUTOR-BOUNDARY FAILURES**. They are not receipts that the configured Python, IL-LLM, Casepath, OpenAPI, ledger, or capability-fabric assertions failed. A workflow conclusion without an executed configured step cannot be promoted into a code-failure claim.

## 3. Pass 3 claim attacked: resident oracle state was not actually persistent in the projection
Pass 3 correctly demanded proof-lineage and projection rehydration, but missed a current-state projection defect in `resident_runtime_controller.py`.

Before Pass 4, each health loop set `oracle_state = None`. The expensive oracle ran only at its interval, yet every non-oracle loop wrote `lastOracle=oracle_state`, replacing the most recent completed oracle result with `null`. Thus the resident controller's state projection preserved current health but discarded the latest validation evidence for most of the controller lifetime.

Pass 4 mutation:
- added `retain_latest_oracle(previous,current)`;
- introduced `latest_oracle_state` as retained controller state;
- a completed oracle replaces the retained value;
- non-oracle health cycles preserve the prior completed result;
- STOPPED projection retains the latest oracle rather than erasing it;
- added `scripts/kex-ci/test_resident_oracle_projection.py`;
- added that regression oracle to KEX Runtime Hardening CI.

Classification after mutation:
- source fix: IMPLEMENTED;
- focused regression oracle: IMPLEMENTED SOURCE;
- executed regression result on GitHub: NOT YET OBSERVED because the GitHub executor boundary remains unresolved;
- resident-host continuity: NOT YET REPROVEN.

## 4. Projection rehydration reclassification
Pass 3's eight recovery classes remain useful, but Pass 4 rejects any implication that retaining the latest oracle equals rehydration proof.

Current classes:
1. canonical carrier rehydration — NOT CURRENTLY REPROVEN;
2. semantic-index rehydration — NOT CURRENTLY REPROVEN;
3. observer/mirror regeneration — NOT CURRENTLY REPROVEN;
4. runtime-process/service rehydration — PARTIAL SUPERVISION SOURCE, destructive proof pending;
5. global IL-LLM topology rehydration — NOT CURRENTLY REPROVEN;
6. definition-lineage rehydration — NOT CURRENTLY REPROVEN;
7. authority/capability rehydration — NOT CURRENTLY REPROVEN;
8. proof-lineage rehydration — IMPROVED PROJECTION CONTINUITY SOURCE, destructive proof pending.

New Pass 4 invariant: **the most recent completed oracle is part of current projection state until superseded, but historical oracle survival is not current verification.**

## 5. Atomic VFS generation / compound-write attack
Pass 4 rechecked the existing hardening primitive. Same-directory temp-write + file fsync + `os.replace` + directory fsync remains a strong single-carrier local replacement mechanism.

Pass 4 does not promote this to compound VFS transactions. The unresolved problem is a logical generation spanning multiple object carriers and derived projections. A valid generation protocol still needs an explicit canonical commit object or equivalent mechanism that binds:

`logical identity + generation + member object hashes + semantic graph root + proof root + publication state`

and must make recovery decide between old committed generation, new committed generation, and incomplete candidate generation.

Current classification:
- single-carrier replacement: IMPLEMENTED SOURCE;
- compound generation commit: NOT IMPLEMENTED;
- crash-consistent multi-object recovery oracle: NOT IMPLEMENTED;
- external provider atomicity: REJECTED as a single transaction claim; outbox/saga/reconciliation remains the appropriate boundary.

## 6. Stale-owner/effect recovery attack
Pass 3's fencing model survives current review. Fresh distributed-systems evidence reinforces the reason: lease expiry does not prevent a paused old owner from later writing; correctness requires monotonically increasing fencing tokens that the protected resource actually checks.

Current repository duplicate suppression still preserves ambiguous INFLIGHT records rather than silently replaying them. That is safer than blind retry, but it is not full recovery.

Required implementation remains:
- owner identity;
- monotonic generation/fence;
- lease/heartbeat where appropriate;
- resource-side rejection of stale fences for local governed resources;
- participant idempotency/readback for external effects;
- EFFECT_AMBIGUOUS as a first-class terminal/reconciliation state when effect truth cannot be established.

Current classification: STALE-OWNER/EFFECT RECOVERY INCOMPLETE.

## 7. Statistical experiment attack
Pass 3 was correct to reject single-value performance claims, but Pass 4 tightens the evidence standard further.

Fresh systems literature continues to show material run-to-run variability even on nominally identical hardware and controlled storage stacks. Therefore repeated samples must be retained as evidence, not collapsed immediately into one median/speedup ratio.

Required next benchmark revision:
- raw sample retention;
- explicit cold/warm/cache regime;
- randomized or counterbalanced baseline/candidate order;
- host/runtime fingerprint;
- median, mean, MAD, standard deviation, p95, p99;
- bootstrap confidence interval for effect size;
- serial dependence / batch analysis for resident sequences;
- memory/index amplification;
- correctness oracle attached to every timing family;
- baseline upgraded from deliberately naive scan to at least one competent indexed/materialized comparator;
- scaling claims described as measured regime fits, not Big-O proof.

Current classification:
- repeated synthetic timing loops: IMPLEMENTED;
- scientifically controlled repeated experiment suite: NOT IMPLEMENTED;
- universal acceleration: REJECTED;
- workload-bounded reduction in repeated semantic work: PLAUSIBLE / EXPERIMENT-REQUIRED.

## 8. Market/paradigm reclassification
Pass 4 does not grandfather Pass 3's differentiation statement. The following remain non-novel independently:
- indexing;
- incremental view maintenance;
- spreadsheet programmability;
- append-only evidence logs;
- scoped capabilities;
- supervisor restart;
- content addressing.

The still-testable differentiated systems hypothesis is their integration under stable logical identities and recursive machine definitions across heterogeneous carriers, with contextual executable lowering, observer projections, current proof state, and re-entry semantics.

This is an architecture/research hypothesis, not a market-performance fact.

## 9. Pass 4 current classifications
| Claim | Pass 4 classification |
|---|---|
| Recursive IL-LLM definition/context substrate | IMPLEMENTED SOURCE |
| Workbook semantic carrier analysis | IMPLEMENTED SOURCE |
| IL-LLM intent-to-capability translation | IMPLEMENTED SOURCE; end-to-end authorization proof pending |
| Latest resident oracle retained in projection | IMPLEMENTED SOURCE IN PASS 4 |
| Resident oracle continuity regression | IMPLEMENTED SOURCE; execution pending |
| Single-carrier atomic replacement | IMPLEMENTED SOURCE |
| Compound KEX/VFS generation commit | NOT IMPLEMENTED |
| Destructive projection rehydration suite | NOT IMPLEMENTED |
| Stale-owner fencing | NOT IMPLEMENTED COMPLETELY |
| External-effect reconciliation | PARTIAL / PARTICIPANT-DEPENDENT |
| Repeated synthetic benchmark | IMPLEMENTED SOURCE |
| Controlled statistical experiment suite | NOT IMPLEMENTED |
| Current GitHub hardening validation | PRE-STEP EXECUTOR BOUNDARY; NO CODE-FAILURE RECEIPT |
| TL2_LIVE | NOT PROMOTED |
| PUBLIC_LIVE | NOT IMPLIED / NOT PROMOTED |
| Universal IL-LLM speedup | REJECTED |
| Workload-bounded semantic-work reduction | PLAUSIBLE HYPOTHESIS |

## 10. Replacement conclusion
Pass 4 replaces Pass 3 as the current interpretation.

The highest-value next proof sequence is:
1. obtain an executor that actually runs the configured CI steps or run branch-equivalent tests on a resident host and capture receipts;
2. execute the new oracle-projection regression;
3. implement compound local KEX/VFS generation commit + crash recovery oracle;
4. implement stale-owner fencing for local governed mutation and participant reconciliation state for external effects;
5. build destructive recovery experiments across the eight rehydration classes;
6. replace benchmark summaries with raw-sample controlled experiments and competent baselines;
7. run Pass 5 against this report as untrusted current input.

No claim in this file survives Pass 5 merely because Pass 4 emitted it.
