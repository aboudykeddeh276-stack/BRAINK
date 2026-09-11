#!/usr/bin/env bash
set -euo pipefail
ROOT="${BRAINK_ROOT:-/opt/braink}"
SERVICE_SRC="$ROOT/deploy/systemd/kex-capability-runner.service"
SERVICE_DST="/etc/systemd/system/kex-capability-runner.service"
RESOLVER="${KEX_SECRET_RESOLVER:-/usr/local/libexec/kex-secret-resolver}"

if [[ ! -f "$ROOT/modules/kex_wbos/capability_runner.py" ]]; then
  echo '{"status":"BLOCKED","reason":"capability runner missing"}'
  exit 2
fi
if [[ ! -x "$RESOLVER" ]]; then
  echo "{\"status\":\"BLOCKED\",\"reason\":\"KEX secret resolver not executable\",\"resolver\":\"$RESOLVER\",\"claimBoundary\":\"KEX secret custody cannot be bypassed.\"}"
  exit 3
fi
sudo install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
sudo systemctl daemon-reload
sudo systemctl enable --now kex-capability-runner.service
sudo systemctl is-active --quiet kex-capability-runner.service
SOCK=/run/keddeh/kex-runner.sock
[[ -S "$SOCK" ]] || { echo '{"status":"FAIL","reason":"runner socket absent after service start"}'; exit 4; }
printf '{"status":"VERIFIED","service":"kex-capability-runner.service","socket":"%s","secretResolver":"KEX_OWNED_AND_BOUND","claimBoundary":"Service and Unix socket are live; provider execution requires an authorized capability request and a valid KEX-resolved credential."}\n' "$SOCK"
