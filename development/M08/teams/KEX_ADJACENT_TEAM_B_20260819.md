# KEX Adjacent Team B — Runtime Closure

Seed: `KEX-TEAM-B-20260819-7F2C91`

## Goal
Advance one continuous evidence-bearing path from the V8 HTML authority surface through the local bridge into the existing BTC vertical closure, without allowing repository state, historical worker receipts, or browser-local simulation to masquerade as live runtime state.

## Shared contract
- HTML authority surface: `KEDDEH_BRAINK_HTML_LAUNCHPAD_v8_EVIDENCE_BEARING_ASSET_AUTHORITY_20260819_7F2C91.html`
- Bridge endpoint contract: `POST http://127.0.0.1:8799/bridge/command`
- Runtime command vocabulary: `CHECK_RPC`, `START_NODE`, `GET_BLOCKCHAIN_INFO`, `REQUEST_TEMPLATE`, `RUN_VERTICAL_CLOSURE`, `START_HASHING`, `STOP_HASHING`, `SUBMIT_BLOCK`.
- BTC integration target: existing `runtime/btc_vertical_closure.py` plus existing consensus/workload modules.
- Evidence rule: presence, wiring, resolution, integrity, persistence, execution and readback remain separate properties.
- V86 RUNNING authority: only a current `emulator-ready` observation can promote the V86 carrier to RUNNING.
- Historical resident-worker evidence is provenance only and cannot mutate current V86 authority.
- GitHub commits are storage/change evidence, not product-state evidence.

## Workers

### TB-01 — Bridge Contract Worker
Scope: `KSYS_CONNECT.py` contract compatibility and adapter mapping.
Outcome: map every HTML command to one explicit bridge handler and one typed readback shape.
Do not edit: BTC consensus algorithms or V86 dependency loader.
Proof: request/response contract fixtures; unknown command must fail closed.

### TB-02 — V86 Authority Worker
Scope: HTML Linux dependency and boot authority path.
Outcome: verify state progression `UNRESOLVED -> VERIFIED_DEPENDENCIES -> CONSTRUCTOR_DISPATCH -> BOOTING -> RUNNING` and every blocked state.
Do not edit: Bitcoin consensus or submit policy.
Proof: only `emulator-ready` may create current V86 RUNNING receipt.

### TB-03 — BTC Core Authority Worker
Scope: Core RPC observation and node lifecycle.
Outcome: preserve Bitcoin Core as protocol/chain authority and expose exact chain/readback fields to the launchpad.
Do not edit: browser credential policy.
Proof: unavailable Core produces blocked receipt, never synthetic SYNCED state.

### TB-04 — Vertical Closure Worker
Scope: `btc_vertical_closure.py`, consensus reconstruction seam, candidate/run binding.
Outcome: trace template -> exact candidate -> SHA256d/target -> freshness -> submit gate.
Do not edit: HTML presentation except documented contract changes.
Proof: stale template, malformed candidate, non-hit and target-hit are distinct states.

### TB-05 — Evidence Ledger Worker
Scope: receipt schemas and failure lineage.
Outcome: unify property-scoped receipts across HTML, bridge, Core and BTC closure without evidence-category promotion.
Do not edit: execution behavior.
Proof: DECLARED/SOURCE_VERIFIED/TESTED/EMPIRICALLY_VERIFIED/PROVEN remain non-interchangeable.

### TB-06 — Security Boundary Worker
Scope: localhost bridge, input validation, secrets, command allowlist, replay/resource boundaries.
Outcome: prove browser never receives RPC cookie/password and arbitrary shell/process invocation is not exposed by bridge commands.
Do not edit: mining math.
Proof: negative contract cases for unknown command, malformed JSON, oversized request, non-local binding policy where applicable.

### TB-07 — Integration Test Worker
Scope: contract and characterization tests only.
Outcome: create a vertical test matrix crossing HTML command semantics, bridge responses, Core unavailable/available states, candidate reconstruction and submission gating.
Do not edit: production behavior unless separately handed back after a failing characterization is established.
Proof: each test names the property it establishes and its environment.

### TB-08 — Regression/Contradiction Worker
Scope: read-only comparison of V6/V8 authority semantics and historical worker receipts.
Outcome: identify any route where old `RESIDENT-WORKER` evidence could incorrectly promote current V86 state or BTC state.
Do not edit: production files.
Proof: evidence-backed contradiction list with exact integration seam.

### TB-09 — Runtime Observability Worker
Scope: logs/readback/receipt correlation.
Outcome: bind one correlation ID across HTML dispatch -> bridge -> BTC workload -> submission/readback.
Do not edit: consensus rules.
Proof: one trace can be followed end-to-end without inferring chronology from filenames or commits.

### TB-10 — Parent Integration Reviewer
Scope: all Team B outputs after worker evidence exists.
Outcome: reconcile overlaps, reject conflicting patches, verify interfaces, and decide integration candidate status.
Do not edit during first review pass.
Proof: Keystone-style spec axis + standards axis review; blockers separated from non-blockers.

## Integration order
1. TB-08 characterization/contradiction report.
2. TB-01 bridge contract + TB-06 security boundary in parallel.
3. TB-02 V86 authority + TB-03 Core authority in parallel because ownership is isolated.
4. TB-04 vertical closure against frozen contracts.
5. TB-05 evidence normalization + TB-09 correlation.
6. TB-07 end-to-end characterization/integration matrix.
7. TB-10 independent integration review.

## Promotion criterion
Team B is not complete because files exist. Promotion requires an observed chain of receipts for the relevant environment. A browser-local state-machine result cannot promote host Core state; a historical worker receipt cannot promote current V86 execution; a GitHub commit cannot promote runtime readiness; and a valid non-hit mining iteration remains a valid execution result without being a solved block.
