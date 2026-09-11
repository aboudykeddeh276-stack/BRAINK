#!/usr/bin/env bash
set -euo pipefail

ROOT="${BRAINK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REPORT_DIR="${BRAINK_REPORT_DIR:-$ROOT/reports/direct-deploy}"
mkdir -p "$REPORT_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$REPORT_DIR/saas-direct-$TS.json"
STRIPE_SERVICE_SRC="$ROOT/deploy/systemd/braink-stripe-payment-rail.service"
STRIPE_SERVICE_DST="/etc/systemd/system/braink-stripe-payment-rail.service"
KEX_SOCKET="${KEX_RUNNER_SOCKET:-/run/keddeh/kex-runner.sock}"
STRIPE_SOCKET="${BRAINK_STRIPE_SOCKET:-/run/keddeh/braink-stripe.sock}"

fail() {
  local reason="$1"
  printf '{"status":"BLOCKED","reason":"%s","report":"%s"}\n' "$reason" "$REPORT" | tee "$REPORT"
  exit 1
}

[[ -f "$ROOT/modules/kex_wbos/capability_runner.py" ]] || fail "KEX_CAPABILITY_RUNNER_MISSING"
[[ -f "$ROOT/runtime/stripe_payment_rail.py" ]] || fail "STRIPE_PAYMENT_RAIL_MISSING"
[[ -f "$STRIPE_SERVICE_SRC" ]] || fail "STRIPE_SERVICE_DEFINITION_MISSING"
[[ -f "$ROOT/deploy/install_kex_capability_runner.sh" ]] || fail "KEX_INSTALLER_MISSING"

# Qualification is local and authoritative. GitHub is not required.
python3 "$ROOT/scripts/kex-ci/test_kex_capability_runner.py"

if [[ -d "$ROOT/runtime/publish/src" ]]; then
  if python3 -c 'import pytest' >/dev/null 2>&1; then
    (cd "$ROOT/runtime/publish" && PYTHONPATH=src python3 -m pytest -q)
  else
    printf '%s\n' 'BRAINK_RUNTIME_TEST_SKIPPED: pytest not resident; no network installation attempted.'
  fi
fi

BRAINK_ROOT="$ROOT" bash "$ROOT/deploy/install_kex_capability_runner.sh"
[[ -S "$KEX_SOCKET" ]] || fail "KEX_SOCKET_NOT_LIVE"

sudo install -m 0644 "$STRIPE_SERVICE_SRC" "$STRIPE_SERVICE_DST"
sudo systemctl daemon-reload
sudo systemctl enable --now braink-stripe-payment-rail.service
sudo systemctl is-active --quiet braink-stripe-payment-rail.service || fail "STRIPE_PAYMENT_RAIL_NOT_ACTIVE"
[[ -S "$STRIPE_SOCKET" ]] || fail "STRIPE_SOCKET_NOT_LIVE"

KEX_PROBE="$(python3 - <<'PY'
import json, os, socket
p=os.environ.get('KEX_RUNNER_SOCKET','/run/keddeh/kex-runner.sock')
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(3); s.connect(p)
s.sendall(b'{"op":"PROBE"}\n'); raw=s.recv(65536); s.close()
r=json.loads(raw.decode()); assert r.get('status')=='REJECTED'; print(json.dumps(r,separators=(',',':')))
PY
)"

STRIPE_PROBE="$(python3 - <<'PY'
import json, os, socket
p=os.environ.get('BRAINK_STRIPE_SOCKET','/run/keddeh/braink-stripe.sock')
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(3); s.connect(p)
s.sendall(b'{"op":"PROBE"}\n'); raw=s.recv(65536); s.close()
r=json.loads(raw.decode()); assert r.get('status')=='REJECTED'; print(json.dumps(r,separators=(',',':')))
PY
)"

python3 - "$REPORT" "$KEX_PROBE" "$STRIPE_PROBE" <<'PY'
import json, socket, sys, time
path,kex,stripe=sys.argv[1:]
body={
  'status':'VERIFIED',
  'deployment':'DIRECT_KEX_FIRST',
  'github_required':False,
  'host':socket.gethostname(),
  'timestamp_ns':time.time_ns(),
  'kex_socket':'/run/keddeh/kex-runner.sock',
  'stripe_socket':'/run/keddeh/braink-stripe.sock',
  'kex_probe':json.loads(kex),
  'stripe_probe':json.loads(stripe),
  'claim_boundary':'Resident services and sockets verified. Provider execution still requires KEX authorization and valid KEX-held credentials.'
}
with open(path,'w',encoding='utf-8') as f: json.dump(body,f,sort_keys=True,indent=2)
print(json.dumps(body,sort_keys=True,indent=2))
PY
