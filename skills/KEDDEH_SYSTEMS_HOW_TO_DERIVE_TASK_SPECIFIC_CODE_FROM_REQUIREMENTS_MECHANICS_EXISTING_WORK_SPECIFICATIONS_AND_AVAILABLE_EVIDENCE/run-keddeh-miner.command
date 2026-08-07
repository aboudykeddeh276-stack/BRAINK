#!/usr/bin/env bash
# Keddeh BTC — production launcher for the live mainnet control plane.
#
# Points the real mechanics at a real, synced Bitcoin Core node. RPC/wallet stay
# private (loopback); only Bitcoin P2P and (optionally) Stratum are ever public.
#
# Usage:
#   ./run-keddeh-miner.command                       # cookie auth + wallet payout
#   KEDDEH_PAYOUT_ADDRESS=bc1q... ./run-keddeh-miner.command
#
# Environment overrides:
#   KEDDEH_RPC_HOST     (default 127.0.0.1)   RPC host — keep private
#   KEDDEH_RPC_PORT     (default 8332)        mainnet RPC port
#   KEDDEH_COOKIE       (default ~/.bitcoin/.cookie)
#   KEDDEH_WALLET       wallet name for /wallet/<name> RPC
#   KEDDEH_PAYOUT_ADDRESS  static payout address (else derive from wallet)
#   KEDDEH_MAX_NONCE    (default 1048576)     bounded local nonce scan
#   KEDDEH_NO_SUBMIT    if set, run the full pipeline but do not submitblock

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${HERE}/src"

RPC_HOST="${KEDDEH_RPC_HOST:-127.0.0.1}"
RPC_PORT="${KEDDEH_RPC_PORT:-8332}"
COOKIE="${KEDDEH_COOKIE:-${HOME}/.bitcoin/.cookie}"
MAX_NONCE="${KEDDEH_MAX_NONCE:-1048576}"

args=(--rpc-host "${RPC_HOST}" --rpc-port "${RPC_PORT}" --cookie "${COOKIE}" --max-nonce "${MAX_NONCE}")

if [[ -n "${KEDDEH_WALLET:-}" ]]; then
  args+=(--wallet "${KEDDEH_WALLET}")
fi

if [[ -n "${KEDDEH_PAYOUT_ADDRESS:-}" ]]; then
  args+=(--payout-address "${KEDDEH_PAYOUT_ADDRESS}")
else
  args+=(--from-wallet)
fi

if [[ -n "${KEDDEH_NO_SUBMIT:-}" ]]; then
  args+=(--no-submit)
fi

cd "${SRC_DIR}"
exec python3 -m btc.live "${args[@]}"
