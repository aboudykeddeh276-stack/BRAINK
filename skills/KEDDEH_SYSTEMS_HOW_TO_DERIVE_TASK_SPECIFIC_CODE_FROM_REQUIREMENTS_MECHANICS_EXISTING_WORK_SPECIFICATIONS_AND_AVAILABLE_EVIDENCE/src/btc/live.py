#!/usr/bin/env python3
"""CLI: point the real BTC mining control plane at a real Bitcoin Core node.

Example (private, cookie-authenticated mainnet node with a static payout address):

    python3 -m btc.live \
        --rpc-host 127.0.0.1 --rpc-port 8332 \
        --cookie ~/.bitcoin/.cookie \
        --payout-address bc1q... \
        --max-nonce 1048576

Or derive a fresh payout from the node's own private wallet:

    python3 -m btc.live --cookie ~/.bitcoin/.cookie --wallet mywallet --from-wallet

This performs REAL RPC I/O. It does not fabricate a node. If ``bitcoind`` is not
reachable it fails at that exact mechanical boundary, as intended.
"""

from __future__ import annotations

import argparse
import json
import sys

from .controller import LiveMinerConfig, LiveMinerError, run_live_attempt
from .payout import payout_script_from_address, payout_script_from_wallet
from .rpc import CoreRpcClient, CoreRpcConfig, RpcError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keddeh BTC live mainnet control plane")
    parser.add_argument("--rpc-host", default="127.0.0.1")
    parser.add_argument("--rpc-port", type=int, default=8332)
    parser.add_argument("--wallet", default=None, help="wallet name for /wallet/<name> RPC")
    auth = parser.add_mutually_exclusive_group(required=True)
    auth.add_argument("--cookie", dest="cookie_path", help="path to Core .cookie file")
    auth.add_argument("--rpc-user", dest="rpc_user", help="rpcauth username")
    parser.add_argument("--rpc-password", dest="rpc_password", help="rpcauth password")
    payout = parser.add_mutually_exclusive_group(required=True)
    payout.add_argument("--payout-address", help="static mainnet payout address")
    payout.add_argument("--from-wallet", action="store_true", help="derive payout via wallet RPC")
    parser.add_argument("--chain", default="main")
    parser.add_argument("--max-nonce", type=int, default=1 << 20)
    parser.add_argument("--allow-nonlocal", action="store_true",
                        help="permit a non-loopback RPC host (secured private network only)")
    parser.add_argument("--no-submit", action="store_true",
                        help="run the full pipeline but do not call submitblock")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.rpc_user and not args.rpc_password:
        print("ERROR: --rpc-password is required with --rpc-user", file=sys.stderr)
        return 2

    try:
        rpc_config = CoreRpcConfig(
            host=args.rpc_host,
            port=args.rpc_port,
            wallet=args.wallet,
            cookie_path=args.cookie_path,
            rpc_user=args.rpc_user,
            rpc_password=args.rpc_password,
            allow_nonlocal=args.allow_nonlocal,
        )
        client = CoreRpcClient(rpc_config)

        if args.from_wallet:
            payout_address, payout_script = payout_script_from_wallet(client)
        else:
            payout_address = args.payout_address
            payout_script = payout_script_from_address(args.payout_address)

        attempt = run_live_attempt(
            client=client,
            payout_script=payout_script,
            config=LiveMinerConfig(expected_chain=args.chain, max_nonce_scan=args.max_nonce),
            submit=not args.no_submit,
        )
    except (LiveMinerError, RpcError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED_AT_BOUNDARY", "error": str(exc)}))
        return 1

    report = {
        "status": "DONE",
        "chain": attempt.chain,
        "height": attempt.height,
        "payout_address": payout_address,
        "target": hex(attempt.target),
        "total_fees": attempt.total_fees,
        "coinbase_value_sat": attempt.coinbase_value,
        "stale": attempt.stale,
        "candidate_found": attempt.candidate_found,
        "block_hash": attempt.block_hash_display,
        "submitted": attempt.submitted,
        "accepted": attempt.submit_result.accepted if attempt.submit_result else None,
        "reject_reason": attempt.submit_result.reject_reason if attempt.submit_result else None,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
