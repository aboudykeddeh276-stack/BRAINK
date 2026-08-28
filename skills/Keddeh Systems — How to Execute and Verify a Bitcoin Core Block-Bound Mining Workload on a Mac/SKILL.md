# Keddeh Systems — How to Execute and Verify a Bitcoin Core Block-Bound Mining Workload on a Mac

## Purpose
Reproduce target-level Bitcoin Core acceptance of the Keddeh Systems corrected block-bound mining workload on a macOS host with public Internet access.

## Core mechanics
Architecture detection → official Bitcoin Core acquisition → checksum verification → isolated regtest authority → content-addressed BRAINK source checkout → source identity verification → cookie-authenticated RPC readiness → real `getblocktemplate` → payout-bearing BIP34/BIP141 block construction → SHA256d target search → stale-tip check → full `submitblock` → Core chain readback → 100-confirmation maturity extension → evidence hashing.

## Reuse decisions
The skill reuses BRAINK `runtime/btc_consensus.py`, `runtime/btc_miner_runtime.py`, and `runtime/btc_workload_substrate.py`. It does not duplicate their consensus/workload implementation. The host harness supplies only target provisioning, execution, and evidence capture.

## Required success evidence
- verified official Bitcoin Core archive SHA-256;
- exact audited BRAINK commit and source blob identities;
- live `getblockchaininfo`;
- live `getblocktemplate`;
- miner result state `ACCEPTED_BY_NODE`;
- `submitblock` result `null` / accepted;
- Core blockcount and best-block readback after submission;
- accepted block readback;
- at least 101 confirmations on the accepted block after extension;
- evidence file SHA-256 ledger.

## Failure logic
Any failed prerequisite, checksum, source identity, RPC readiness, template acquisition, miner return, Core acceptance, chain readback, or maturity assertion terminates fail-closed and preserves the run evidence directory. No failed target gate is translated into a hardware or architecture impossibility.

## Claim boundary
Passing this skill proves real Bitcoin Core **regtest** acceptance and coinbase-maturity mechanics for the corrected workload on the executing Mac. It does not by itself prove mainnet block discovery, physical ASIC capacity, joules/hash, accepted pool shares, or realised profit.
