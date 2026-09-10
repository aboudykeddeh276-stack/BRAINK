#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${BRAINK_REPO_ROOT:-/opt/braink}"
UNIT_SOURCE="${REPO_ROOT}/deployment/kex-signal-fabric.service"
UNIT_TARGET="/etc/systemd/system/kex-signal-fabric.service"
ENV_DIR="/etc/braink"
ENV_FILE="${ENV_DIR}/signal-fabric.env"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root" >&2
  exit 2
fi

for command in python3 systemctl install curl; do
  command -v "${command}" >/dev/null 2>&1 || { echo "ERROR: missing ${command}" >&2; exit 3; }
done

[[ -d "${REPO_ROOT}" ]] || { echo "ERROR: repository root not found: ${REPO_ROOT}" >&2; exit 4; }
[[ -f "${UNIT_SOURCE}" ]] || { echo "ERROR: service unit not found: ${UNIT_SOURCE}" >&2; exit 5; }

python3 -m py_compile \
  "${REPO_ROOT}/runtime/signal_fabric.py" \
  "${REPO_ROOT}/runtime/signal_service.py" \
  "${REPO_ROOT}/runtime/estate_signal_handlers.py"

mkdir -p "${ENV_DIR}"
chmod 0750 "${ENV_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -z "${KEX_SIGNAL_AUTH_TOKEN:-}" || -z "${KEX_SIGNAL_AUTHORITY:-}" ]]; then
    echo "ERROR: ${ENV_FILE} absent. Supply KEX_SIGNAL_AUTH_TOKEN and KEX_SIGNAL_AUTHORITY for first install." >&2
    exit 6
  fi
  umask 077
  printf 'KEX_SIGNAL_AUTH_TOKEN=%q\nKEX_SIGNAL_AUTHORITY=%q\n' \
    "${KEX_SIGNAL_AUTH_TOKEN}" "${KEX_SIGNAL_AUTHORITY}" > "${ENV_FILE}"
fi

chmod 0600 "${ENV_FILE}"
grep -q '^KEX_SIGNAL_AUTH_TOKEN=' "${ENV_FILE}" || { echo "ERROR: KEX_SIGNAL_AUTH_TOKEN missing from ${ENV_FILE}" >&2; exit 7; }
grep -q '^KEX_SIGNAL_AUTHORITY=' "${ENV_FILE}" || { echo "ERROR: KEX_SIGNAL_AUTHORITY missing from ${ENV_FILE}" >&2; exit 8; }

install -m 0644 "${UNIT_SOURCE}" "${UNIT_TARGET}"
systemctl daemon-reload
systemctl enable --now kex-signal-fabric.service

for _ in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:18033/healthz | grep -q 'kex.signal/1'; then
    echo "KEX_SIGNAL_FABRIC_HOST_ACTIVATION=PASS"
    systemctl --no-pager --full status kex-signal-fabric.service || true
    exit 0
  fi
  sleep 0.25
done

systemctl --no-pager --full status kex-signal-fabric.service || true
journalctl -u kex-signal-fabric.service -n 80 --no-pager || true
echo "KEX_SIGNAL_FABRIC_HOST_ACTIVATION=FAIL" >&2
exit 9
