#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export BRAINK_OPERATOR_AUTHORITY="${BRAINK_OPERATOR_AUTHORITY:-USER_OPERATOR}"
export BRAINK_AUTH_TOKEN="${BRAINK_AUTH_TOKEN:-change-me}"
export BRAINK_TELEMETRY_SPREADSHEET_ID="${BRAINK_TELEMETRY_SPREADSHEET_ID:-1nGeP43FHviLsVzM58Tp4RIMXG1MYs_51Wda8gtbfOVo}"
export BRAINK_TELEMETRY_RANGE="${BRAINK_TELEMETRY_RANGE:-TCP_SOCKET_TELEMETRY!B11:N17}"
export BRAINK_MINING_PROVIDER="${BRAINK_MINING_PROVIDER:-VIABTC_BTC}"
export BRAINK_MINING_ACCOUNT="${BRAINK_MINING_ACCOUNT:-aboudykeddeh276}"
export BRAINK_MINING_MANIFEST="${BRAINK_MINING_MANIFEST:-$ROOT/data/mining_orchestration_manifest.json}"
export BRAINK_HOST_NETWORK_MODE="${BRAINK_HOST_NETWORK_MODE:-validate}"

printf 'BRAINK operator authority: %s\n' "$BRAINK_OPERATOR_AUTHORITY"
printf 'Host: %s\n' "$(hostname)"
printf 'Mining provider profile: %s\n' "$BRAINK_MINING_PROVIDER"
printf 'Host network mode: %s\n' "$BRAINK_HOST_NETWORK_MODE"

# Host-level validation/mutation must run on the operator host, never inside the
# application container. PYTHONPATH points at the resident package without
# requiring a prior installation.
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  bash "$ROOT/scripts/apply_host_network_profile.sh"

validate_orchestration() {
  python -m braink_runtime.mining_orchestration \
    --provider "$BRAINK_MINING_PROVIDER" \
    --account "$BRAINK_MINING_ACCOUNT" \
    --out "$BRAINK_MINING_MANIFEST" >/tmp/braink-mining-orchestration.json
}

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose build braink-runtime
  docker compose run --rm --no-deps braink-runtime \
    python -m braink_runtime.mining_orchestration \
      --provider "$BRAINK_MINING_PROVIDER" \
      --account "$BRAINK_MINING_ACCOUNT" \
      --out /data/mining_orchestration_manifest.json
  docker compose up -d braink-runtime
  docker compose run --rm telemetry-qualifier
  docker compose ps
elif command -v python3 >/dev/null 2>&1; then
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e .
  validate_orchestration
  nohup uvicorn braink_runtime.casepath_app:app --host 127.0.0.1 --port 8000 > /tmp/braink-runtime.log 2>&1 &
  RUNTIME_PID=$!
  trap 'kill "$RUNTIME_PID" >/dev/null 2>&1 || true' EXIT
  READY=0
  for _ in $(seq 1 30); do
    if python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1)
except Exception:
    raise SystemExit(1)
PY
    then READY=1; break; fi
    sleep 1
  done
  if [ "$READY" -ne 1 ]; then
    echo 'BRAINK runtime failed health readback.' >&2
    exit 3
  fi
  python scripts/qualify_live_telemetry.py
else
  echo 'No supported host runtime found: need Docker Compose or Python 3.' >&2
  exit 2
fi

python - <<'PY'
from __future__ import annotations
import hashlib, json, os, platform, socket, time
from pathlib import Path
root = Path.cwd()
manifest_path = Path(os.environ["BRAINK_MINING_MANIFEST"])
qual_path = root / "data" / "live_telemetry_qualification.json"
receipt = {
    "schema": "braink.operator.deployment.receipt.v1",
    "timestamp_ns": time.time_ns(),
    "authority": os.environ.get("BRAINK_OPERATOR_AUTHORITY", "USER_OPERATOR"),
    "host": {"hostname": socket.gethostname(), "platform": platform.platform()},
    "provider": os.environ.get("BRAINK_MINING_PROVIDER", "VIABTC_BTC"),
    "host_network_mode": os.environ.get("BRAINK_HOST_NETWORK_MODE", "validate"),
    "orchestration_manifest": json.loads(manifest_path.read_text()) if manifest_path.exists() else None,
    "live_qualification": json.loads(qual_path.read_text()) if qual_path.exists() else None,
}
out = root / "data" / "operator_deployment_receipt.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(f"Operator deployment receipt: {out}")
print(f"SHA256: {hashlib.sha256(out.read_bytes()).hexdigest()}")
PY

printf '\nOrchestration manifest: %s\n' "$BRAINK_MINING_MANIFEST"
printf 'Qualification receipt: %s\n' "$ROOT/data/live_telemetry_qualification.json"
printf 'Operator deployment receipt: %s\n' "$ROOT/data/operator_deployment_receipt.json"
