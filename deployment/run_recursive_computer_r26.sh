#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="${BRAINK_R26_STATE_ROOT:-${ROOT}/.braink/r26/computer-A}"
HOST="${BRAINK_R26_HOST:-127.0.0.1}"
PORT="${BRAINK_R26_PORT:-8811}"
COMPUTER_ID="${BRAINK_R26_COMPUTER_ID:-A}"

mkdir -p "${STATE_ROOT}"
exec python3 "${ROOT}/deployment/recursive_computer_service_r26.py" \
  --state-root "${STATE_ROOT}" \
  --computer-id "${COMPUTER_ID}" \
  --host "${HOST}" \
  --port "${PORT}"
