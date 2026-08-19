# BTC-SFI-E01 — Live Vertical Closure

Status: IMPLEMENTATION CANDIDATE — LIVE CORE PROOF PENDING

## Governing invariant

Preserve one Bitcoin object lineage from Core-authoritative template acquisition to the submission boundary. Correct components do not qualify the run unless the exact objects remain causally bound.

`Core → GBT → Coinbase → Merkle/Witness → Header → SHA256d → Candidate → submitblock`

## Implemented in this branch

`runtime/btc_mining_lineage.py` introduces `MiningRun`, an identity/evidence envelope around the existing `btc_consensus.py` candidate builder. It does not replace the consensus implementation.

The run binds:

- canonical template digest;
- previous block hash and height;
- deterministic run identity;
- exact header bytes to the first 80 bytes of the complete block;
- reconstructed SHA256d/block hash;
- template bits and previous hash;
- network-target predicate;
- current-tip freshness predicate;
- append-only digest-linked evidence receipts.

The submission gate is fail-closed. A valid candidate with no target hit produces `NOT_TRIGGERED`, not failure and not acceptance. A stale tip independently blocks submission.

## Required live experiment

1. Resolve a synchronized real Bitcoin Core endpoint.
2. Record `getrpcinfo`, `getblockchaininfo`, and `getbestblockhash` receipts.
3. Acquire one current `getblocktemplate` with SegWit rule support.
4. Create `MiningRun.from_template(template)`.
5. Build the payout-bearing candidate through existing `btc_consensus.py`.
6. Independently reconstruct and verify candidate lineage.
7. Feed the exact reconstructed header into the existing SHA256d/sharding implementation.
8. If no network target is found, retain a normal no-candidate result and request/follow current work according to freshness rules.
9. If a target is found, recheck Core tip and require `MiningRun.submission_gate(...).submission_ready == True`.
10. Submit the exact preserved `block_hex`; retain Core's exact response separately from local qualification.

## Falsification conditions

- Productive hashing continues after Core authority disappears.
- Candidate header is not byte-identical to the complete block's first 80 bytes.
- Candidate previous hash or bits diverge from the bound template.
- A candidate from another run/template can pass verification.
- Stale work reaches submission.
- No-target is classified as implementation failure.
- Local/CI/workbook/synthetic evidence advances node acceptance.
- This lineage layer replaces a stronger existing Core/consensus implementation instead of wrapping it.

## Evidence boundary

This branch proves source-level lineage mechanics only until tests are executed in a compatible checkout and the live Core experiment is observed. It makes no claim of a mainnet target hit, `submitblock` acceptance, active-chain inclusion, coinbase maturity, spendable BTC, or profitability.
