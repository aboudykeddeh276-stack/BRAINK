"""Canonical BTC mining mechanics — one authoritative implementation each.

This package embodies the working principle:

    One mechanic, one authoritative implementation, many consumers.
    Tests verify mechanics; they do not recreate them.
    Packaging relocates mechanics; it does not redefine them.
    Repository organisation describes mechanics; it does not become another
    execution architecture.

Each module implements exactly one mechanic of the BTC assembly/execution chain:

    template -> coinbase -> witness commitment -> merkle root -> header
             -> work -> hash -> candidate -> full block -> submit

`pipeline.py` composes these same functions; tests, runtime, CLI, and any package
all consume the identical implementations rather than rewriting them.

Live control plane (real mainnet execution, private-by-default topology):

    rpc.py        real Bitcoin Core JSON-RPC transport (cookie/rpcauth, private host)
    address.py    address -> scriptPubKey (bech32/bech32m/base58check)
    payout.py     coinbase payout-script derivation (static address or wallet RPC)
    controller.py getblockchaininfo -> getblocktemplate -> pipeline -> submitblock
    telemetry.py  revenue/cost profitability from measured hashrate + live target
    stratum.py    Stratum V1 worker boundary (subscribe/authorize/notify/submit)
    live.py       CLI that points the mechanics at a real synced Core node

Core RPC and wallet RPC stay on the private control plane; only Stratum (worker
boundary) and Bitcoin P2P are ever exposed publicly.
"""
