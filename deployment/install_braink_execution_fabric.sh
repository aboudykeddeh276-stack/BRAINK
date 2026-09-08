#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="${BRAINK_INSTALL_ROOT:-/opt/braink}"
RELEASES="$INSTALL_ROOT/releases"
CURRENT="$INSTALL_ROOT/current"
SERVICE_NAME="braink-execution.service"
SERVICE_DST="/etc/systemd/system/$SERVICE_NAME"
ENV_DIR="/etc/braink"
ENV_FILE="$ENV_DIR/execution.env"
STATE_DIR="${BRAINK_EXECUTION_STATE:-/var/lib/braink/resident-execution}"
SOCKET="${BRAINK_EXECUTION_SOCKET:-/run/braink/execution.sock}"
MODE="${1:-install}"

require() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING_COMMAND:$1" >&2; exit 10; }; }
require python3

if git -C "$ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
  RELEASE_ID="$(git -C "$ROOT" rev-parse HEAD)"
else
  require sha256sum
  RELEASE_ID="tree-$(find "$ROOT" -type f -not -path '*/.git/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
fi
RELEASE_DIR="$RELEASES/$RELEASE_ID"

python3 -m py_compile \
  "$ROOT/enterprise/orchestration/resident_execution_fabric.py" \
  "$ROOT/deployment/braink_execution_service.py" \
  "$ROOT/deployment/braink_execctl.py" \
  "$ROOT/enterprise/runtime/process_supervisor.py" \
  "$ROOT/runtime/runtime_route_registry.py"
python3 "$ROOT/scripts/kex-ci/test_resident_execution_fabric.py"

if [[ "$MODE" == "preflight" ]]; then
  printf '{"status":"PREFLIGHT_PASS","release_id":"%s","source":"%s"}\n' "$RELEASE_ID" "$ROOT"
  exit 0
fi
if [[ "$MODE" != "install" ]]; then
  echo "USAGE:$0 [preflight|install]" >&2
  exit 12
fi

require systemctl
require tar
if [[ "$EUID" -ne 0 ]]; then
  echo "ROOT_REQUIRED" >&2
  exit 11
fi

PREVIOUS_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"
ACTIVATED=0
rollback() {
  rc=$?
  if [[ $rc -ne 0 && $ACTIVATED -eq 1 ]]; then
    echo "ROLLBACK_BEGIN" >&2
    if [[ -n "$PREVIOUS_TARGET" && -d "$PREVIOUS_TARGET" ]]; then
      ln -sfn "$PREVIOUS_TARGET" "$CURRENT"
      systemctl daemon-reload || true
      systemctl restart "$SERVICE_NAME" || true
      echo "ROLLBACK_RESTORED:$PREVIOUS_TARGET" >&2
    else
      systemctl disable --now "$SERVICE_NAME" || true
      echo "ROLLBACK_DISABLED_NEW_SERVICE" >&2
    fi
  fi
  exit "$rc"
}
trap rollback EXIT

mkdir -p "$RELEASES" "$ENV_DIR" "$STATE_DIR"
chmod 0700 "$ENV_DIR" "$STATE_DIR"

if [[ ! -d "$RELEASE_DIR" ]]; then
  mkdir -p "$RELEASE_DIR"
  tar -C "$ROOT" --exclude=.git --exclude='runtime/resident-execution' -cf - . | tar -C "$RELEASE_DIR" -xf -
fi

if [[ ! -f "$ENV_FILE" ]]; then
  KEY_HEX="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  umask 077
  printf 'BRAINK_EXECUTION_HMAC_KEY_HEX=%s\n' "$KEY_HEX" > "$ENV_FILE"
fi
chmod 0600 "$ENV_FILE"

install -m 0644 "$RELEASE_DIR/deployment/braink-execution.service" "$SERVICE_DST"
ln -sfn "$RELEASE_DIR" "$CURRENT"
ACTIVATED=1
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

for _ in $(seq 1 80); do
  [[ -S "$SOCKET" ]] && break
  sleep 0.1
done
test -S "$SOCKET"
[[ "$(stat -c '%a' "$SOCKET")" == "600" ]]

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export BRAINK_EXECUTION_SOCKET="$SOCKET"
export BRAINK_EXECUTION_STATE="$STATE_DIR"
export BRAINK_EXECUTION_SIGNER_STATE="$STATE_DIR"

HEALTH_BEFORE="$(python3 "$CURRENT/deployment/braink_execctl.py" --socket "$SOCKET" health)"
WORK_ID="activation-${RELEASE_ID:0:12}-$(date +%s)"
DISPATCH="$(python3 "$CURRENT/deployment/braink_execctl.py" --socket "$SOCKET" dispatch antigravity-deploy DESCRIBE_ROUTE --work-id "$WORK_ID" --actor-type DEPLOYMENT_AUTHORITY --actor-id owner-host-installer)"
READBACK="$(python3 "$CURRENT/deployment/braink_execctl.py" --socket "$SOCKET" readback "$WORK_ID")"

systemctl restart "$SERVICE_NAME"
for _ in $(seq 1 80); do
  [[ -S "$SOCKET" ]] && break
  sleep 0.1
done
test -S "$SOCKET"
[[ "$(stat -c '%a' "$SOCKET")" == "600" ]]
HEALTH_AFTER="$(python3 "$CURRENT/deployment/braink_execctl.py" --socket "$SOCKET" health)"
READBACK_AFTER="$(python3 "$CURRENT/deployment/braink_execctl.py" --socket "$SOCKET" readback "$WORK_ID")"

python3 - "$RELEASE_ID" "$RELEASE_DIR" "$PREVIOUS_TARGET" "$WORK_ID" "$HEALTH_BEFORE" "$DISPATCH" "$READBACK" "$HEALTH_AFTER" "$READBACK_AFTER" <<'PY'
import json, sys
release_id, release_dir, previous, work_id, *raw = sys.argv[1:]
health_before, dispatch, readback, health_after, readback_after = map(json.loads, raw)
assert health_before.get('status') == 'PASS', health_before
assert dispatch.get('status') == 'COMPLETED', dispatch
assert len(dispatch.get('proof','')) == 64, dispatch
assert readback.get('status') == 'PASS', readback
assert health_after.get('status') == 'PASS', health_after
assert readback_after.get('status') == 'PASS', readback_after
assert readback_after['work']['state'] == 'COMPLETED', readback_after
assert [e['state'] for e in readback_after['events']] == ['ADMITTED','EXECUTING','COMPLETED'], readback_after
print(json.dumps({
  'status':'ACTIVATED_AND_REHYDRATED',
  'release_id':release_id,
  'release_dir':release_dir,
  'previous_release':previous or None,
  'work_id':work_id,
  'proof_root':dispatch['proof'],
  'socket_mode':'0600',
  'service':'braink-execution.service',
  'health_before_restart':health_before,
  'health_after_restart':health_after,
  'rehydrated_readback_state':readback_after['work']['state'],
}, sort_keys=True))
PY

ACTIVATED=0
trap - EXIT
