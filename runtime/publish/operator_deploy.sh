#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export BRAINK_OPERATOR_AUTHORITY="${BRAINK_OPERATOR_AUTHORITY:-USER_OPERATOR}"
export BRAINK_AUTH_TOKEN="${BRAINK_AUTH_TOKEN:-change-me}"
export BRAINK_TELEMETRY_SPREADSHEET_ID="${BRAINK_TELEMETRY_SPREADSHEET_ID:-1nGeP43FHviLsVzM58Tp4RIMXG1MYs_51Wda8gtbfOVo}"
export BRAINK_TELEMETRY_RANGE="${BRAINK_TELEMETRY_RANGE:-TCP_SOCKET_TELEMETRY!B11:N17}"

printf 'BRAINK operator authority: %s\n' "$BRAINK_OPERATOR_AUTHORITY"
printf 'Host: %s\n' "$(hostname)"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d --build braink-runtime
  docker compose run --rm telemetry-qualifier
  docker compose ps
elif command -v python3 >/dev/null 2>&1; then
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e .
  nohup uvicorn braink_runtime.casepath_app:app --host 127.0.0.1 --port 8000 > /tmp/braink-runtime.log 2>&1 &
  RUNTIME_PID=$!
  trap 'kill "$RUNTIME_PID" >/dev/null 2>&1 || true' EXIT
  for _ in $(seq 1 30); do
    if python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1)
except Exception:
    raise SystemExit(1)
PY
    then break; fi
    sleep 1
  done
  python scripts/qualify_live_telemetry.py
else
  echo 'No supported host runtime found: need Docker Compose or Python 3.' >&2
  exit 2
fi

printf '\nReceipt: %s\n' "$ROOT/data/live_telemetry_qualification.json"
