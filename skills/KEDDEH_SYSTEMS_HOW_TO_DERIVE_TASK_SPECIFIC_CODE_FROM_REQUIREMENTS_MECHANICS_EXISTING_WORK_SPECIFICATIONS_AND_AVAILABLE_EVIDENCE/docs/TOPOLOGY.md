# Keddeh BTC Mining — Live Mainnet Topology

Full-live means **real mainnet execution**, not "expose every interface publicly."
Each interface is reachable **only where its function requires it**. Bitcoin Core's
own guidance is explicit: the JSON-RPC interface must **not** be exposed to the
public Internet, because RPC credentials grant significant control over the node
and wallet (see `bitcoin/doc/JSON-RPC-interface.md`).

## The real execution chain

```
REAL Bitcoin mainnet
  -> REAL Bitcoin Core node
  -> REAL current chain state          (getblockchaininfo / getbestblockhash)
  -> REAL getblocktemplate
  -> REAL wallet/payout script         (control plane only)
  -> REAL coinbase + witness commitment + Merkle root
  -> REAL work distributed to hashing hardware
  -> REAL SHA256d search
  -> REAL candidate reconstruction
  -> REAL submitblock
  -> REAL Core acceptance/rejection
  -> REAL revenue/cost telemetry
```

Nothing in that chain requires simulation. The difficulty of mainnet simply makes
a found block improbable within a bounded local nonce scan — that is honest reality,
not a simulation substituted for the target.

## Public vs private boundary

```
                     PUBLIC INTERNET
                    /               \
             Bitcoin P2P        Remote ASICs
               :8333                 |
                 |               Stratum TCP
                 |                   |
        +--------v-------------------v--------+
        |          KEDDEH MINING HOST         |
        |                                     |
        |  Stratum worker service  (public)   |
        |            |                        |
        |  prepared-work controller           |
        |            |                        |
        |  candidate reconstruction           |
        |            |                        |
        |  profitability telemetry            |
        |                                     |
        |          PRIVATE ONLY               |
        |            |                        |
        |     Core RPC 127.0.0.1:8332         |
        |            |                        |
        |       Bitcoin Core                  |
        |            |                        |
        |     wallet/<walletname>             |
        +-------------------------------------+
```

| Interface            | Exposure          | Rationale                                        |
|----------------------|-------------------|--------------------------------------------------|
| Bitcoin P2P `:8333`  | Public (optional) | Normal node reachability; carries no credentials |
| Stratum V1           | Public if remote  | Correct worker boundary; ships jobs, not secrets |
| Core JSON-RPC `:8332`| **Private only**  | Credentials control node + wallet                |
| Wallet RPC           | **Private only**  | Scoped `/wallet/<name>`; touches keys            |
| Cookie / `rpcauth`   | **Private only**  | Grants node control                              |
| Wallet files / keys  | **Private only**  | Never leave the host                             |

## What the hashing worker receives — and never receives

A Stratum worker (ASIC) needs only:

```
job id, previous hash, coinbase halves + extranonce domain,
Merkle branch, version, nBits, nTime, share target
```

It must **never** receive:

```
wallet credentials, Core RPC credentials, private keys, wallet files
```

The payout script is derived once in the control plane (`payout.py`), then only the
resulting job crosses the worker boundary (`stratum.py`).

## Code map

| Boundary                       | Module          | Exposure         |
|--------------------------------|-----------------|------------------|
| Core JSON-RPC transport        | `src/btc/rpc.py`        | private   |
| Address -> scriptPubKey        | `src/btc/address.py`    | control plane |
| Payout-script derivation       | `src/btc/payout.py`     | control plane |
| Template -> submit controller  | `src/btc/controller.py` | control plane |
| Stratum V1 worker messages     | `src/btc/stratum.py`    | public boundary |
| Revenue/cost telemetry         | `src/btc/telemetry.py`  | monitoring |
| CLI entry point                | `src/btc/live.py`       | operator |

`rpc.py` is **private by default**: it refuses a non-loopback / non-private RPC host
unless the operator explicitly sets `allow_nonlocal=True` for a deliberately secured
private network.

## Running against a real synced node

```
python3 -m btc.live \
    --rpc-host 127.0.0.1 --rpc-port 8332 \
    --cookie ~/.bitcoin/.cookie \
    --payout-address bc1qyourpayoutaddress...
```

Or derive a fresh payout from the node's own private wallet:

```
python3 -m btc.live --cookie ~/.bitcoin/.cookie --wallet mywallet --from-wallet
```

Use `--no-submit` to run the full real pipeline without broadcasting a block, and
`--allow-nonlocal` only when the RPC host is a secured private-network address.

If `bitcoind` is unreachable or unsynced, the run fails **at that exact mechanical
boundary** and reports `FAILED_AT_BOUNDARY` — it does not fabricate a node.

## Bitcoin Core configuration

See `resources/production/bitcoin.conf.template`. Key invariants:

- `server=1`, `rpcbind=127.0.0.1`, `rpcallowip=127.0.0.1` — RPC stays on loopback.
- `txindex` not required; `blockfilterindex` optional.
- P2P (`:8333`) may accept inbound connections; RPC (`:8332`) never should.
- Prefer cookie auth; if using `rpcauth`, keep the secret off the worker network.
