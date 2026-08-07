# Keddeh Systems — How to Derive Task-Specific Code from Requirements, Mechanics, Existing Work, Specifications, and Available Evidence

**Canonical identifier:** `KEDDEH_SYSTEMS_HOW_TO_DERIVE_TASK_SPECIFIC_CODE_FROM_REQUIREMENTS_MECHANICS_EXISTING_WORK_SPECIFICATIONS_AND_AVAILABLE_EVIDENCE`
**Version:** 1.0.0
**Methodology reference:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`

## Purpose

Derive and validate the **task-specific code and executable capability** required by a
process. The governing object is the code that implements a required capability — never
the act of obtaining a tool. The **underlying mechanics are the true highlights of the
function**: they causally produce the capability, so they, not any single domain, are
what this skill reasons about.

This skill is **domain-general**. It reasons over any capability specification that
follows the schema in `src/derive_task_specific_code.py`. The Bitcoin Core / BTC mining
pipeline in `resources/btc_case_study.json` is one **clear, direct, amendable case
study** applied to that general engine — the Bitcoin protocol is illustrative, not a
locked topic.

**Scope:** any capability that can be decomposed into mechanics → functions → required
knowledge/reference/oracles → derivation pathways.
**Excluded:** treating "obtain / download tool X" as the primary requirement; promoting a
single failed acquisition route to a capability-level limitation.

## Governing rule

> The requirement is the capability-specific code. Acquisition methods exist only to
> supply knowledge, source, reference implementations, or test oracles required to
> derive and validate that code. **A failed acquisition method cannot be promoted into a
> capability limitation while other derivation pathways remain available or untested.**

## Derivation hierarchy

```text
REQUIRED CAPABILITY
    -> REQUIRED MECHANICS          (the true highlights of the function)
    -> REQUIRED CODE (functions)
    -> REQUIRED KNOWLEDGE / REFERENCE / TEST ORACLE
    -> DERIVATION PATHWAYS
```

Acquisition — and `download` inside it — sit at the **bottom**, as subordinate routes:

```text
Download  (subset of)  Acquisition  (subset of)  Derivation Pathways
```

The wrong abstraction (rejected by this skill):

```text
need tool X -> download X -> environment cannot download -> blocked
```

## Assumptions

- Python 3.10+ standard library is available; no external packages are required.
- A capability is expressed as a specification object with `capability` and a non-empty
  `mechanics` list, each mechanic carrying at least one `derivation_pathways` entry.
- Pathway statuses are drawn from `available`, `untested`, `tested_and_failed`,
  `ruled_out_with_evidence`.
- Reference corpora (existing source, existing implementations, specifications,
  mathematics, test vectors) are inputs to analysis, not architectural dependencies by
  default.

## Core mechanics

1. Decompose the required capability into mechanics; decompose each mechanic into
   functions with explicit inputs, outputs, state, invariants, errors, and interfaces.
2. Attach to each mechanic the required knowledge and the candidate **derivation
   pathways** (specification, mathematics, existing source, connected repository,
   package cache, source archive, git clone, binary release, download, user-supplied
   artifact, published test vectors, reference/independent implementation).
3. Order pathways by canonical priority so acquisition (and download) is evaluated at
   its correct subordinate level (`PATHWAY_PRIORITY`).
4. Classify each mechanic:
   - `MECHANIC_IS_DERIVABLE` — at least one pathway is `available`.
   - `EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN` — no available pathway, but a pathway
     remains `untested` (never a limitation).
   - `CAPABILITY_LIMITATION_ALL_PATHWAYS_EXHAUSTED` — every pathway is exhausted with
     evidence (`tested_and_failed` or `ruled_out_with_evidence`).
5. Roll mechanic verdicts up to a capability verdict and a stable exit code.

## Interfaces

```text
Entry point:   python3 src/derive_task_specific_code.py <capability_spec.json>
               python3 src/derive_task_specific_code.py --case-study btc
               python3 src/derive_task_specific_code.py --list-case-studies
Stdin:         not used
Stdout:        JSON derivation report
Stderr:        human-readable per-mechanic summary
Exit codes:    0 = capability fully derivable
               1 = a mechanic is a proven capability limitation, or input unreadable
               2 = a mechanic has insufficient evidence (status unknown)
```

## State

The engine is stateless: each invocation reads a specification, evaluates it, and emits a
report. The only durable state is the amendable case-study data under `resources/`.

## Invariants

1. Every mechanic in the specification appears in the report with exactly one verdict.
2. A mechanic with any `available` pathway is `MECHANIC_IS_DERIVABLE`; its selected route
   is the highest-priority available pathway.
3. A mechanic whose only non-exhausted pathways are `untested` is never reported as a
   capability limitation.
4. A mechanic is a capability limitation only when **every** pathway is
   `tested_and_failed` or `ruled_out_with_evidence`.
5. When all failed pathways are acquisition routes, `failure_is_acquisition_only` is
   `true`, signalling that non-acquisition derivation must be attempted before any
   limitation claim.
6. The capability verdict is `HAS_PROVEN_LIMITATION` if any mechanic is a limitation,
   else `STATUS_UNKNOWN...` if any is unknown, else `IS_FULLY_DERIVABLE`.

## Failure classifications

- `SPEC_STRUCTURE_ERROR` — the capability specification violates its structural contract
  (raised as `SpecError`).
- `INPUT_UNREADABLE` — the spec file cannot be read or parsed as JSON.
- `EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN` — a mechanic cannot yet be judged derivable
  or limited; more routes must be tested before any negative claim.

## Governing doctrine: capability is the centre

Capability — software whose behaviour, structure, performance, and reliability are
demonstrably strong — is the centre of the workflow. Evidence is a **by-product** of that
capability, never a substitute for it.

```text
UNDERSTAND THE REQUIRED MECHANIC
 -> FIT EXISTING USEFUL LOGIC
 -> DERIVE WHAT IS MISSING
 -> BUILD THE REAL FUNCTION
 -> CONNECT IT DIRECTLY
 -> RUN IT -> BREAK IT -> FIX IT
 -> MEASURE IT -> OPTIMISE IT
 -> REPEAT UNTIL THE SOFTWARE ITSELF IS EXCELLENT
```

Then tests, logs, benchmarks, receipts, and claims simply describe what the software
already demonstrably does:

> A test exists because it helps make the software better.
> A benchmark exists because it tells us where to improve.
> A log exists because it reveals what happened.
> A skill exists because it preserves a proven engineering method.
> A module exists because it performs a real function.
> A repository exists because it stores the work.

The working loop is therefore:

```text
ACHIEVE -> VERIFY -> IMPROVE -> VERIFY AGAIN -> PRESERVE THE MECHANICS
```

not `CLASSIFY -> DOCUMENT -> GATE -> EXPLAIN -> eventually build`. And, consistent with the
governing rule above: **do not spend effort proving why something cannot be done while
plausible engineering pathways remain — exhaust the pathways first.**

The derivation engine (`src/derive_task_specific_code.py`) is a *planning aid* subordinate
to this doctrine: it enumerates pathways so building proceeds, and prevents a failed
acquisition route from masquerading as a limitation. It does not replace building,
running, breaking, measuring, and improving the real software.

## Working principle: one mechanic, one implementation, many consumers

A mechanic is written **once**, as a single authoritative function. The repository stores
it, tests call it, runtime calls it, the CLI calls it, CI runs its tests, and a package
distributes it. None of those contexts re-implement business logic.

```text
MECHANIC
    -> canonical implementation
        - repository representation   (stores it)
        - test invocation             (calls it, verifies via an oracle)
        - runtime invocation          (calls it)
        - CLI invocation              (calls it)
        - CI invocation               (runs its tests)
        - packaged invocation         (distributes it)
```

Consequences enforced by this skill:

> Tests verify mechanics; they do not recreate them.
> Packaging relocates mechanics; it does not redefine them.
> Repository organisation describes mechanics; it does not become another execution
> architecture.

Formally, engineering work is `mechanics + minimal representations required to execute
and verify them`, never `mechanics × every representation`.

## BTC case study (amendable) — two faithful projections

The BTC mining pipeline is provided in two complementary, non-duplicating forms.

**1. Derivation-planning projection — `resources/btc_case_study.json`.**
Data consumed by the general engine to reason about *how each mechanic is derived*. Its
mechanics — the highlights — include RPC contract, block-template interpretation, BIP34
coinbase, payout scripts, BIP141 witness commitment, transaction Merkle construction,
80-byte header, work-space allocation, SHA256d execution, candidate reconstruction,
target verification, full-block assembly, stale-work handling, `submitblock`, and economic
accounting. The `submitblock` mechanic deliberately records a **failed `download`**
acquisition route alongside available specification and untested source/reference routes;
the engine still reports it derivable — demonstrating the governing rule in executable
form. Amend the file (add mechanics, adjust pathway statuses, cite new evidence) and
re-run the engine to re-derive the verdict.

**2. Executable-mechanics projection — `src/btc/`.**
The direct mechanical chain, one authoritative function per mechanic, consumed by
`src/btc/pipeline.py` and by the tests:

```text
src/btc/
    serialize.py    # shared byte primitives (sha256d, CompactSize, endianness)
    template.py     # get_template / parse_block_template
    economics.py    # block_subsidy / coinbase_value
    bip34.py        # encode_bip34_height
    coinbase.py     # build_coinbase_tx / coinbase_txid
    witness.py      # BIP141 witness_commitment_script
    merkle.py       # merkle_root
    header.py       # build_header / block_hash
    work.py         # allocate_work
    mining.py       # search_nonce (SHA256d) / reconstruct_candidate
    target.py       # bits_to_target / meets_target
    block.py        # assemble_block
    stale.py        # is_stale
    submit.py       # build_submitblock_request / interpret response (transport-free)
    measure.py      # measured SHA256d execution rate + economics (benchmark)
    pipeline.py     # composes the above: template -> ... -> submit
```

Correctness is anchored to independent oracles: the real Bitcoin **genesis block** header
hash, Merkle root, and target are reproduced exactly, and a regtest-style easy target lets
the full chain run end-to-end without network access. To dry-run the chain, call
`btc.pipeline.run_pipeline` (see `tests/test_btc_mechanics.py`).

## Claim boundary

| Claim | Status |
|---|---|
| Domain-general derivation engine implemented | TRUE |
| Acquisition modeled as subordinate to derivation | TRUE |
| Failed acquisition not promoted to limitation while pathways remain | TRUE |
| Amendable BTC case study provided | TRUE |
| Executable BTC mechanics implemented once and composed in a pipeline | TRUE |
| BTC mechanics verified against the real genesis block and independent oracles | TRUE |
| Miner measures real SHA256d execution rate and economics | TRUE |
| Engine and case study tested | TRUE |
| Download required at runtime | FALSE — no network access is required |
