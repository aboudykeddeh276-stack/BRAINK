#!/usr/bin/env bash
# Keddeh BTC — production launcher for the continuous live mainnet control plane.
#
# The normal lifecycle does not require a Start Mining action. Once this launcher is
# active it keeps resolving Core work, hashing, cancelling stale work, rolling work
# space, submitting candidates and retrying until the process is explicitly stopped.
#
# Usage:
#   ./run-keddeh-miner.command                       # cookie auth + wallet payout
#   KEDDEH_PAYOUT_ADDRESS=bc1q... ./run-keddeh-miner.command
#
# Environment overrides:
#   KEDDEH_RPC_HOST       (default 127.0.0.1)
#   KEDDEH_RPC_PORT       (default 8332)
#   KEDDEH_COOKIE         (default ~/.bitcoin/.cookie)
#   KEDDEH_WALLET         wallet name for /wallet/<name> RPC
#   KEDDEH_PAYOUT_ADDRESS static payout address (else derive from wallet)
#   KEDDEH_MAX_NONCE      (default 1048576) nonce window per work round
#   KEDDEH_WORKERS        (default 4) concurrent KEX worker lanes
#   KEDDEH_STALE_POLL     (default 1.0) Core tip observation interval seconds
#   KEDDEH_RETRY_INITIAL  (default 1.0) transient RPC retry delay seconds
#   KEDDEH_RETRY_MAX      (default 30.0) maximum transient RPC retry delay seconds
#   KEDDEH_NO_SUBMIT      if set, candidates are not submitted
#   KEDDEH_ONCE           if set, execute one bounded diagnostic attempt then exit

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${HERE}/src"

RPC_HOST="${KEDDEH_RPC_HOST:-127.0.0.1}"
RPC_PORT="${KEDDEH_RPC_PORT:-8332}"
COOKIE="${KEDDEH_COOKIE:-${HOME}/.bitcoin/.cookie}"
MAX_NONCE="${KEDDEH_MAX_NONCE:-1048576}"
WORKERS="${KEDDEH_WORKERS:-4}"
STALE_POLL="${KEDDEH_STALE_POLL:-1.0}"
RETRY_INITIAL="${KEDDEH_RETRY_INITIAL:-1.0}"
RETRY_MAX="${KEDDEH_RETRY_MAX:-30.0}"

args=(
  --rpc-host "${RPC_HOST}"
  --rpc-port "${RPC_PORT}"
  --cookie "${COOKIE}"
  --max-nonce "${MAX_NONCE}"
  --workers "${WORKERS}"
  --stale-poll "${STALE_POLL}"
  --retry-initial "${RETRY_INITIAL}"
  --retry-max "${RETRY_MAX}"
)

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

if [[ -n "${KEDDEH_ONCE:-}" ]]; then
  args+=(--once)
fi

cd "${SRC_DIR}"
exec python3 -m btc.live "${args[@]}"
