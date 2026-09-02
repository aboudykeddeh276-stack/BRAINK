# IL-LLM Recursive Review Contract R1

## Governing Principle
Pass N+1 MUST attack Pass N with the same or greater rigor that Pass N applied to the original source estate.

No artifact receives inherited credibility because it was generated, reviewed, benchmarked, documented, classified, or approved in a prior pass.

## Pass N Becomes Source Material
The complete output of Pass N becomes the current system-under-review for Pass N+1, including:

- reports and determinations
- market-impact claims
- case studies and paradigm mappings
- benchmark designs, measurements, ratios, scaling claims, and interpretations
- capability classifications
- implementation-state classifications
- architecture diagrams and abstractions
- source modules and APIs
- workbook semantics and IL-LLM graph structures
- tests and test oracles
- security decisions and threat models
- proof/readback rules
- READMEs and documentation
- continuation records
- rejection criteria
- the review methodology itself

## No Grandfathering
Nothing is accepted in Pass N+1 merely because Pass N said it was IMPLEMENTED, EXECUTED, VERIFIED, SECURE, PERFORMANT, NOVEL, MARKET-RELEVANT, ARCHITECTURALLY CORRECT, or PRODUCTION-READY.

A prior verifier result is historical evidence only. Survival is not validation. Pass N+1 is forbidden from citing Pass N as "already validated" merely because it survived the prior verifier.

## Mandatory Reclassification
At the start of every pass, every prior claim MUST be reclassified against current artifacts and current evidence:

- IMPLEMENTED: source or configuration materially exists.
- EXECUTED: the relevant runtime path was actually run.
- VERIFIED: execution produced independent or contract-defined readback supporting the claim.
- INFERRED: supported by architecture or evidence but not directly demonstrated.
- HYPOTHESIS: plausible claim requiring new evidence.
- STALE: previously accurate but no longer supported by the current estate.
- REJECTED: contradicted by current evidence or invalid reasoning.

No previous classification is inherited automatically.

## Required Pass N+1 Attack Surface
Each new pass MUST independently evaluate:

1. Claim correctness.
2. Evidence quality.
3. Classification correctness.
4. Architecture fitness.
5. Security and authority containment.
6. Runtime/data/graph/proof correctness.
7. Complexity and scaling behavior.
8. Concurrency and duplicate-execution hazards.
9. Operability and recovery.
10. Provenance and readback lineage.
11. Benchmark validity.
12. Market validity using fresh sources where current evidence matters.
13. Paradigm mapping validity.
14. Documentation fidelity.
15. Review-method validity.
16. Projection rehydration fidelity.
17. Atomic VFS mutation semantics.
18. Stale-lock detection and recovery.
19. Repeated-experiment statistical stability.

## Projection Rehydration Gate
A projection is not canonical state. Every pass that relies on HTML, workbook projection, observer view, cached graph, generated report, or other derived surface MUST test rehydration from canonical state.

Required properties:
- canonical identity survives projection loss and regeneration;
- graph/object lineage survives rehydration;
- observer-relative views can be reconstructed without becoming canonical authority;
- stale projection state is detectable;
- regenerated projection hashes/receipts are attributable to the canonical state used;
- rehydration cannot silently promote a projection-only mutation into canonical state.

A projection claim is VERIFIED only after destructive or clean-start rehydration reproduces the required invariants.

## Atomic VFS Write Gate
Any VFS-backed canonical mutation MUST use an atomic commit discipline appropriate to its substrate.

For filesystem carriers this normally means:
1. validate complete candidate state before mutation;
2. write to a sibling temporary object;
3. flush file content and required metadata;
4. fsync the temporary file where supported;
5. atomically replace/rename the canonical carrier;
6. fsync the containing directory where supported;
7. preserve required permissions/ownership;
8. emit proof only after the canonical carrier is observable;
9. regenerate or invalidate dependent projections/semantic sidecars transactionally.

Partial writes, torn JSON, stale sidecars, and mutation receipts emitted before durable replacement are correctness failures.

## Stale-Lock Recovery Gate
Locks are runtime coordination state, not permanent authority objects.

Every lock implementation MUST define:
- owner identity;
- acquisition generation/nonce;
- acquisition timestamp;
- heartbeat or lease semantics where cross-process persistence exists;
- stale-owner detection;
- recovery/fencing rule;
- proof event for forced recovery;
- protection against an old owner resuming after a newer owner has been fenced in.

A simple age timeout is insufficient when ownership can still be alive. Recovery must distinguish dead/stale ownership from slow but valid work whenever the host substrate permits it.

Where advisory OS locks disappear automatically on process death, any persistent lock metadata MUST still be reconciled against actual ownership on restart.

## Repeated Statistical Experiment Gate
A benchmark or market-performance claim MUST NOT be promoted from a single run.

Each performance pass MUST, where execution is available:
- perform warm-up separately from measured trials;
- run repeated independent trials per estate/workload size;
- retain raw per-trial observations;
- report at least N, median, mean, dispersion (standard deviation or robust equivalent), and p95 where latency is relevant;
- report confidence intervals or bootstrap intervals for comparative ratios when sample count permits;
- randomize or counterbalance baseline/IL-LLM execution order when shared-host drift can bias results;
- record machine/runtime/version configuration;
- separate cold-start, warm-resident, incremental-update, and rehydration experiments;
- test multiple estate sizes and fit scaling only when the model fit is justified;
- preserve failed/outlier trials rather than silently deleting them;
- rerun the experiment in Pass N+1 rather than citing Pass N statistics as current proof.

A claimed speedup MUST include the numerator and denominator distributions, not only a ratio. A scaling exponent MUST include goodness-of-fit and the tested N range. Synthetic workload results MUST remain classified separately from real-estate/runtime measurements.

## Fresh Market and Research Rule
Pass N+1 MUST rerun market assumptions and external paradigm research against fresh sources where claims depend on current science, products, standards, competitors, market conditions, or software practice.

Prior case-study determinations are reopened by default. They are not immutable citations.

## Retest Rule
Where execution is available, Pass N+1 MUST retest prior implementation claims instead of relying solely on historical receipts.

Where execution is unavailable, the pass MUST state that limitation explicitly and downgrade any claim that depends on execution evidence.

## Replacement Current-State Corpus
Every completed pass MUST emit a replacement current-state corpus. It supersedes the previous corpus as the authoritative interpretation of the current estate.

The replacement corpus MUST include:
- current claim ledger;
- current file/module capability map;
- current evidence classification;
- current unresolved defect register;
- current benchmark/readback results and raw experiment references;
- current rehydration and VFS-integrity results;
- current stale-lock/recovery results;
- current paradigm/case-study determinations;
- current market-impact determinations;
- current invalid or retracted claims;
- current continuation state.

Historical passes remain available only for lineage, regression analysis, and explaining how conclusions changed.

## Recursive Cycle
PASS N:
1. Snapshot repository/runtime/documentation/claims.
2. Build claim-to-artifact map.
3. Re-read implementation.
4. Reclassify all claims.
5. Threat-model, correctness-review, complexity-review, concurrency-review, provenance-review.
6. Test projection rehydration, VFS atomicity, and stale-lock recovery where relevant.
7. Research external paradigms and current market evidence.
8. Implement qualified improvements.
9. Add hostile tests and benchmark oracles.
10. Execute repeated statistical experiments and readbacks where possible.
11. Generate replacement current-state corpus.
12. Record unresolved issues and continuation state.

PASS N+1:
Treat every output from PASS N as untrusted current input and repeat the entire cycle from step 1.

## Promotion Law
A claim may be promoted only from current evidence, never from historical status alone.

SOURCE RESIDENT != EXECUTED
EXECUTED != VERIFIED
VERIFIED IN PASS N != AUTOMATICALLY VERIFIED IN PASS N+1
PROJECTION PRESENT != CANONICAL STATE
SINGLE SUCCESSFUL RUN != STATISTICAL SYSTEM PROPERTY
ATOMIC API INTENT != DURABLE ATOMIC WRITE
LOCK FILE PRESENT != LIVE OWNER
LOCAL VERIFIED != TL2_LIVE
TL2_LIVE != PUBLIC_LIVE
BENCHMARK RESULT != GENERAL MARKET PERFORMANCE
PARADIGM SIMILARITY != PARADIGM EQUIVALENCE
DOCUMENTED != IMPLEMENTED

## IL-LLM Integration
The review corpus itself is an IL-LLM input layer.

Definitions, claims, evidence classes, source modules, workbook objects, tests, market facts, rejected claims, projections, lock/recovery events, experiment distributions, and review determinations MUST remain machine-addressable and traversable so a future pass can query:

- what defines a capability;
- what evidence supports it;
- which pass promoted it;
- which later pass challenged it;
- which source/runtime/workbook/VFS objects implement it;
- which projection was derived from it;
- whether rehydration reproduced it;
- which statistical experiment supports a performance claim;
- which market assumptions depend on it;
- which proof/readback artifacts validate it;
- which contradictions remain unresolved.

This creates definitions of definitions over the engineering process itself.

## Failure Condition
A recursive review pass is incomplete if it merely confirms the previous pass, updates wording without re-evaluating evidence, treats the prior determination as authoritative because it is recent, relies on a single benchmark run for a scaling claim, fails to test projection rehydration, permits non-atomic canonical VFS writes, or lacks a stale-lock recovery rule for persistent coordination state.
