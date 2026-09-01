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
Nothing is accepted in Pass N+1 merely because Pass N said it was:

- IMPLEMENTED
- EXECUTED
- VERIFIED
- SECURE
- PERFORMANT
- NOVEL
- MARKET-RELEVANT
- ARCHITECTURALLY CORRECT
- PRODUCTION-READY

A prior verifier result is historical evidence only. Survival is not validation.

Pass N+1 is forbidden from citing Pass N as "already validated" merely because it survived the prior verifier.

## Mandatory Reclassification
At the start of every pass, every prior claim MUST be reclassified against the current artifacts and current evidence using the following evidence classes:

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

1. Claim correctness: does the current implementation actually support the words used?
2. Evidence quality: is the evidence execution/readback evidence, or source presence/configuration only?
3. Classification correctness: were prior evidence labels assigned correctly?
4. Architecture fitness: is the prior abstraction still the best representation after the latest findings?
5. Security: can authority leak, widen, bypass IL-LLM translation, or survive outside intended scope?
6. Correctness: can runtime, workbook, graph, proof, or service state become internally inconsistent?
7. Complexity: did the previous pass introduce O(N), O(N^2), unbounded, recursive, or duplicated work that invalidates its scaling claim?
8. Concurrency: can races, stale caches, duplicate execution, or split ownership corrupt state?
9. Operability: can the runtime recover, supervise, re-enter, and preserve identity under failure?
10. Provenance: can every promoted claim be traced to source, runtime state, or independent readback?
11. Benchmark validity: are the workload, baseline, warm/cold state, sample size, scaling model, and metrics scientifically appropriate?
12. Market validity: do current external sources still support the claimed market need, differentiation, and impact?
13. Paradigm mapping: does the imported external paradigm still map mechanically, or was the analogy overstated?
14. Documentation fidelity: do READMEs and reports still describe the exact current system?
15. Review-method validity: did the previous review process itself miss classes of failure or bias the result?

## Fresh Market and Research Rule
Pass N+1 MUST rerun market assumptions and external paradigm research against fresh sources where those claims depend on current science, products, standards, competitors, market conditions, or software practice.

Prior case-study determinations are reopened by default. They are not immutable citations.

## Retest Rule
Where execution is available, Pass N+1 MUST retest prior implementation claims instead of relying solely on historical receipts.

Where execution is unavailable, the pass MUST state that limitation explicitly and downgrade any claim that depends on execution evidence.

## Replacement Current-State Corpus
Every completed pass MUST emit a replacement current-state corpus. It does not append credibility to the previous corpus; it supersedes it as the authoritative interpretation of the current estate.

The replacement corpus MUST include:

- current claim ledger
- current file/module capability map
- current evidence classification
- current unresolved defect register
- current benchmark/readback results
- current paradigm/case-study determinations
- current market-impact determinations
- current invalid or retracted claims
- current continuation state

Historical passes remain available only for lineage, regression analysis, and explaining how conclusions changed.

## Recursive Cycle
PASS N:
1. Snapshot repository/runtime/documentation/claims.
2. Build claim-to-artifact map.
3. Re-read implementation.
4. Reclassify all claims.
5. Threat-model, correctness-review, complexity-review, concurrency-review, and provenance-review.
6. Research external paradigms and current market evidence.
7. Implement qualified improvements.
8. Add hostile tests and benchmark oracles.
9. Execute and read back where possible.
10. Generate replacement current-state corpus.
11. Record unresolved issues and continuation state.

PASS N+1:
Treat every output from PASS N as untrusted current input and repeat the entire cycle from step 1.

## Promotion Law
A claim may be promoted only from current evidence, never from historical status alone.

SOURCE RESIDENT != EXECUTED
EXECUTED != VERIFIED
VERIFIED IN PASS N != AUTOMATICALLY VERIFIED IN PASS N+1
LOCAL VERIFIED != TL2_LIVE
TL2_LIVE != PUBLIC_LIVE
BENCHMARK RESULT != GENERAL MARKET PERFORMANCE
PARADIGM SIMILARITY != PARADIGM EQUIVALENCE
DOCUMENTED != IMPLEMENTED

## IL-LLM Integration
The review corpus itself is an IL-LLM input layer.

Definitions, claims, evidence classes, source modules, workbook objects, tests, market facts, rejected claims, and review determinations MUST remain machine-addressable and traversable so that a future pass can query not only a capability, but:

- what defines it
- what evidence supports it
- which pass promoted it
- which later pass challenged it
- which source/runtime objects implement it
- which market assumptions depend on it
- which proof/readback artifacts validate it
- which contradictions remain unresolved

This creates definitions of definitions over the engineering process itself.

## Failure Condition
A recursive review pass is incomplete if it merely confirms the previous pass, updates wording without re-evaluating evidence, or treats the prior determination as authoritative because it is recent.
