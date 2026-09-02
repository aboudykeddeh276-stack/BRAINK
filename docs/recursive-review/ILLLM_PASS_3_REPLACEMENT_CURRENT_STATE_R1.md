# IL-LLM Recursive Engineering Review — Pass 3

Status: REPLACEMENT CURRENT-STATE CORPUS FOR PASS 3
Input under attack: `ILLLM_PASS_2_REPLACEMENT_CURRENT_STATE_R1.md`

## 1. Pass 3 posture
Pass 2 is treated as untrusted current source material. Its imported transaction model, recovery taxonomy, benchmark protocol, market statement, and novelty corrections are re-opened.

## 2. Pass 2 overcorrection: conventional mechanisms are not automatically the KEX/VFS model
Pass 2 proposed `intent/WAL -> immutable stage -> commit manifest/root -> atomic root advance`. Mechanically this is credible, but Pass 3 rejects adopting it as the canonical KEX/VFS architecture until it is mapped to KEX identity semantics.

The required KEX/VFS question is not merely "what file is current?" but:
- what logical object identity survives carrier replacement;
- what definition/provenance chain identifies that object;
- what observer projection is derived from it;
- what executable state belongs to the object versus its projection;
- what proof root identifies the committed state;
- what rollback/re-entry transition is valid.

Pass 3 therefore refines the recommendation:

`KEX_IDENTITY -> candidate immutable carrier/object set -> semantic dependency closure -> validation -> commit descriptor(root identity + object hashes + graph/proof bindings + generation) -> atomic canonical-generation switch -> projection hydration -> independent readback`.

The commit descriptor is not the identity. It is evidence that one generation of the identity became canonical.

## 3. Rehydration taxonomy expanded again
Pass 2's four classes still omit global topology and definition lineage.

Pass 3 current recovery classes:
1. canonical carrier rehydration;
2. semantic-index rehydration;
3. observer/mirror projection regeneration;
4. runtime-process/service rehydration;
5. **global IL-LLM topology rehydration** across local/context/sector roots;
6. **definition-lineage rehydration** preserving definition-of-definition chains;
7. **authority/capability rehydration** that reconstructs policy but does not resurrect expired delegated authority;
8. **proof-lineage rehydration** that reconstructs verification state without promoting historical proof into current verification.

Pass 3 determination: the phrase `projection rehydration` is acceptable only as an umbrella term with explicit sub-class evidence.

## 4. Rehydration must test drift, not only equality
Pass 2 focused on reconstruction equivalence. Pass 3 adds drift experiments:
- canonical mutation while projection is offline;
- semantic-rule/version change during rehydration;
- workbook formula/parser version change;
- sector ontology change;
- revoked capability during runtime restart;
- corrupted/stale sidecar;
- missing cross-repository carrier;
- partial proof-history availability.

Correct behavior may be `REHYDRATED_WITH_VERSION_TRANSITION`, `STALE_REJECTED`, or `REBUILD_REQUIRED`, not byte equality.

## 5. Atomic VFS writes: current strongest defensible state
Current source proves a strong atomic local replacement primitive for single carriers, but no repository evidence reviewed in these passes proves a complete logical VFS commit protocol.

Pass 3 classification:
- local single-carrier atomic replacement primitive: IMPLEMENTED;
- compound object-family transaction: HYPOTHESIS/DESIGN REQUIRED;
- KEX generation commit descriptor: RECOMMENDED, NOT IMPLEMENTED;
- crash-consistent projection publication: NOT VERIFIED;
- cross-repository atomicity: REJECTED AS A SINGLE-TRANSACTION CLAIM unless a distributed protocol is materially implemented.

Pass 3 deliberately rejects trying to make every repository/provider mutation globally atomic. For external participants, saga/outbox/reconciliation semantics are more realistic than pretending a filesystem root pointer can atomically commit Google, DNS, GitHub, mail, and local VFS together.

## 6. Stale-lock recovery becomes ownership + effect reconciliation
Pass 2 was correct to split stale lock from participant effects. Pass 3 sharpens the state machine:

`RESERVED(fence,generation,owner)`
`-> EFFECT_NOT_STARTED | EFFECT_PENDING | EFFECT_CONFIRMED | EFFECT_AMBIGUOUS`
`-> COMPLETED | COMPENSATED | MANUAL_RECONCILIATION`

Rules:
- a new owner must carry a monotonically newer fence;
- an old owner may not publish completion after fencing;
- lease expiry alone permits ownership takeover, not blind effect replay;
- external effects require participant idempotency key or readback oracle;
- if neither exists, the action remains ambiguous rather than being retried automatically;
- stale persistent metadata is reconciled against live OS/process ownership on boot.

Pass 3 classification of current idempotency subsystem remains: duplicate suppression implemented; stale-owner/effect recovery incomplete.

## 7. Statistical experiments: Pass 2's "independent trials" assumption is attacked
Resident systems are often non-stationary. Trials may be autocorrelated because:
- term/definition indices grow;
- allocator/cache state changes;
- OS page cache warms;
- Python GC phases vary;
- thermal/power management changes;
- supervisor generations/restarts alter state;
- workbook/graph deltas permanently modify the estate.

Therefore a simple `N >= 30 independent trials` rule is insufficient.

Pass 3 experimental protocol:
### A. Immutable-query microbenchmarks
- freeze estate snapshot;
- randomize AB/BA ordering;
- repeated trials with raw samples;
- median/mean/MAD/stddev/p95/p99;
- bootstrap confidence interval;
- check serial autocorrelation or compare blocked batches;
- report host/runtime fingerprint.

### B. Stateful incremental-update experiments
- start each replicate from a controlled snapshot OR model sequence number explicitly;
- measure update number and affected closure;
- report latency versus graph size and delta size;
- distinguish steady-state from compaction/rebuild events;
- report memory amplification and index growth.

### C. Rehydration experiments
- repeated destructive restart/rebuild trials;
- measure recovery-time distribution, correctness failures, state drift, and proof continuity;
- include injected corruption/stale-state cases.

### D. Long-running resident experiment
- time-series latency and memory over hours/events where execution substrate permits;
- use rolling distributions rather than pretending every sample is iid;
- capture supervisor/recovery events alongside performance.

## 8. Scaling-law attack
Pass 2 retained scaling exponents as useful with R². Pass 3 adds:
- three estate sizes are insufficient for a serious asymptotic conclusion;
- fitted exponent over a narrow range is descriptive, not proof of Big-O;
- query selectivity and graph density must vary independently of N;
- delta closure size must be controlled/measured;
- memory hierarchy effects can change regimes.

Therefore `alpha_ILLLM < alpha_baseline` is a research observable, not an architectural theorem.

## 9. Market comparison attack
Fresh external evidence shows that incremental materialized views, hydration, in-memory indexed views, and self-correcting view maintenance are active production capabilities in contemporary data systems. Spreadsheets are also established programming environments with first-class functions and semantic/programming research.

Therefore Pass 2 is correct that neither incremental maintenance nor spreadsheet programmability alone is differentiating.

Pass 3, however, finds Pass 2 too reductive about workbook value. The advantage can still be large because workbooks combine:
- formula dependency graphs;
- human-maintained data state;
- domain naming/table organization;
- interactive projection;
- executable functions;
- existing sector workflows;
- a widespread authoring surface.

The differentiated hypothesis is not "spreadsheets are code". It is:

**Can KEX/IL-LLM preserve workbook computational semantics as one first-class object family inside a broader cross-sector definition/runtime/authority/proof graph, while retaining the workbook as a usable human projection?**

That is a materially richer and testable claim.

## 10. IL-LLM acceleration claim after three attacks
The strongest current statement is:

IL-LLM is designed to shift work from repeated semantic reconstruction toward maintained machine-addressable definitions, typed relationships, contextual indices, executable routes, and incremental dependency maintenance. When relevant context and update closures are substantially smaller than the global estate, this design can reduce work. The magnitude, end-to-end effect, memory cost, correctness, and scaling regime remain workload-dependent experimental questions.

This statement survives Pass 3.

The following do not survive:
- universal speedup;
- speedup inferred from naive-scan ratios;
- novelty inferred from incremental computation alone;
- novelty inferred from workbook computation alone;
- "verified rehydration" without destructive current-pass trials;
- "atomic VFS" from atomic rename alone.

## 11. Security/execution determination
Pass 3 retains the architectural value of IL-LLM as an intent-to-capability translation layer, but source presence alone does not prove end-to-end enforcement.

Required enforcement proof:
`caller intent -> entered global context -> selected object/route -> capability mint -> downstream facade forwarding -> actuator target check -> effect -> readback -> proof -> re-entry`.

Any facade that drops capability scope, any readback that leaks bearer authority, or any actuator bypassing translation invalidates the complete security claim even if the translator module is correct.

## 12. Pass 3 current classifications
| Claim | Pass 3 classification |
|---|---|
| KEX/IL-LLM recursive definition substrate | IMPLEMENTED SOURCE |
| local/contextual IL-LLM traversal | IMPLEMENTED SOURCE |
| workbook computational semantics carrier | IMPLEMENTED SOURCE; IMPORTANT INTEGRATION HYPOTHESIS |
| single-carrier atomic replacement | IMPLEMENTED |
| logical KEX/VFS generation commit | NOT IMPLEMENTED |
| distributed/cross-provider atomic VFS | REJECTED AS CURRENT CLAIM |
| canonical rehydration | NOT CURRENTLY REPROVEN |
| semantic-index rehydration | NOT CURRENTLY REPROVEN |
| observer/mirror projection regeneration | NOT CURRENTLY REPROVEN |
| global topology/definition-lineage rehydration | NOT CURRENTLY REPROVEN |
| stale-owner recovery | NOT IMPLEMENTED COMPLETELY |
| external effect reconciliation | PARTIAL/ACTUATOR-DEPENDENT |
| repeated synthetic timing | IMPLEMENTED |
| controlled statistical experiment suite | NOT IMPLEMENTED YET |
| asymptotic scaling change | HYPOTHESIS |
| semantic-work reduction mechanism | STRUCTURALLY SUPPORTED HYPOTHESIS |
| end-to-end phenomenal speedup | UNVERIFIED |
| workbook + definitions + authority + execution + proof integration differentiation | PLAUSIBLE MARKET/ARCHITECTURE HYPOTHESIS |

## 13. Replacement current-state corpus conclusion
After three recursive attacks, the architecture that remains strongest is not a claim of magical AI speed. It is a concrete systems direction:

`stable machine identities + recursive definitions + heterogeneous computational carriers (especially workbooks/code/state) + contextual traversal + incremental maintenance + observer projections + scoped executable lowering + durable proof/re-entry`.

The next engineering frontier is no longer more descriptive architecture. It is a proof program:
1. implement KEX/VFS generation commit semantics for compound local object families;
2. implement stale-owner fencing and participant reconciliation;
3. implement destructive rehydration oracles across all eight recovery classes;
4. replace the benchmark with controlled/raw-sample statistical experiments and stronger optimized baselines;
5. repair active security/proof review defects;
6. execute on a resident host and produce current-pass receipts;
7. run Pass 4 against this entire report as untrusted current input.

## 14. Pass 3 supersession rule
This file supersedes Pass 2 as the current interpretation of the branch. Pass 1 and Pass 2 remain only as lineage and evidence of changed reasoning.

Pass 4 is forbidden from treating this Pass 3 report as validated merely because it survived three prior cycles.
