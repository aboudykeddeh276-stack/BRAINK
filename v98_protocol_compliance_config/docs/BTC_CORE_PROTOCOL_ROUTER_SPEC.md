# V99 BTC Core Protocol Router Specification

## Purpose

This document codeifies the uploaded HEMOS Core Node Protocol and Network Integration Matrix into a bounded executable service. The source document asks for a production-grade Bitcoin Core infrastructure interface with P2P wire handling, JSON-RPC, append-only logging, asynchronous task control and market matrix analysis.

The implementation preserves the valid engineering target while correcting execution boundaries:

- Bitcoin P2P message serialization is executable.
- JSON-RPC is optional and read-only unless target-host credentials are supplied by environment variables.
- Market analysis is simulation-only and cannot claim real order execution or realized profit.
- No private key or WIF generation is performed.
- No hard-coded RPC password is embedded.
- Ledger writes are receipts, not ISO certification.

## Executable service

The implementation lives in:

```text
src/keddeh_btc_core_protocol_router.py
```

It provides:

- `BitcoinP2PMessageFactory`
- `BitcoinCoreRPCBridge`
- `AtomicJsonlLedger`
- `ArbitrageAnalyzer`
- `HEMOSBitcoinCoreRouter`

## User operation

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_btc_core_protocol_router.py --root . --once --emit-receipt
python3 -m unittest tests.test_btc_core_protocol_router -v
```

## Outputs

```text
evidence/btc_core_protocol_router_receipt.json
runtime_volume/btc_core_protocol_router.ledger
runtime_volume/outbox/btc_core_protocol_router/*.handoff.json
```

## Target-host live RPC gate

Live Bitcoin Core JSON-RPC requires a local or explicitly configured bitcoind endpoint and these environment variables:

```text
BITCOIN_RPC_URL
BITCOIN_RPC_USER
BITCOIN_RPC_PASSWORD
```

Without those variables, the bridge remains disabled and the service still executes the bounded P2P serialization and receipt path.

## Boundary

The service does not claim Bitcoin Core consensus participation, mining reward, financial trade execution, external certification, ISO audit status, or provider attestation. Those are separate target-host or external assurance gates.
