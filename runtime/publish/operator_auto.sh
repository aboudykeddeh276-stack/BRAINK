#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export BRAINK_OPERATOR_AUTHORITY="${BRAINK_OPERATOR_AUTHORITY:-USER_OPERATOR}"
export BRAINK_AGENT_MAX_ATTEMPTS="${BRAINK_AGENT_MAX_ATTEMPTS:-3}"
export BRAINK_AGENT_BACKOFF_S="${BRAINK_AGENT_BACKOFF_S:-2}"

exec python3 "$ROOT/scripts/operator_agent.py"
