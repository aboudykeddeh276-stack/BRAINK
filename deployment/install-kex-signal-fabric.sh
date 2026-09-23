#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${BRAINK_REPO_ROOT:-/opt/braink}"
SIGNAL_UNIT_SOURCE="${REPO_ROOT}/deployment/kex-signal-fabric.service"
SIGNAL_UNIT_TARGET="/etc/systemd/system/kex-signal-fabric.service"
COPILOT_UNIT_SOURCE="${REPO_ROOT}/deployment/braink-copilot.service"
COPILOT_UNIT_TARGET="/etc/systemd/system/braink-copilot.service"
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
[[ -f "${SIGNAL_UNIT_SOURCE}" ]] || { echo "ERROR: signal service unit not found: ${SIGNAL_UNIT_SOURCE}" >&2; exit 5; }
[[ -f "${COPILOT_UNIT_SOURCE}" ]] || { echo "ERROR: copilot service unit not found: ${COPILOT_UNIT_SOURCE}" >&2; exit 10; }
[[ -f "${REPO_ROOT}/web/braink-copilot/index.html" ]] || { echo "ERROR: copilot front surface missing" >&2; exit 11; }

python3 -m py_compile \
  "${REPO_ROOT}/runtime/signal_fabric.py" \
  "${REPO_ROOT}/runtime/signal_service.py" \
  "${REPO_ROOT}/runtime/estate_signal_handlers.py" \
  "${REPO_ROOT}/runtime/copilot_api.py"

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

install -m 0644 "${SIGNAL_UNIT_SOURCE}" "${SIGNAL_UNIT_TARGET}"
install -m 0644 "${COPILOT_UNIT_SOURCE}" "${COPILOT_UNIT_TARGET}"
systemctl daemon-reload
systemctl enable --now kex-signal-fabric.service
systemctl enable --now braink-copilot.service

for _ in $(seq 1 30); do
  signal="$(curl -fsS http://127.0.0.1:18033/healthz || true)"
  copilot="$(curl -fsS http://127.0.0.1:8080/healthz || true)"
  if printf '%s' "$signal" | grep -q 'kex.signal/1' && printf '%s' "$copilot" | grep -q 'BRAINK_COPILOT'; then
    echo "KEX_SIGNAL_FABRIC_HOST_ACTIVATION=PASS"
    echo "BRAINK_COPILOT_HOST_ACTIVATION=PASS"
    systemctl --no-pager --full status kex-signal-fabric.service || true
    systemctl --no-pager --full status braink-copilot.service || true
    exit 0
  fi
  sleep 0.25
done

systemctl --no-pager --full status kex-signal-fabric.service || true
systemctl --no-pager --full status braink-copilot.service || true
journalctl -u kex-signal-fabric.service -n 80 --no-pager || true
journalctl -u braink-copilot.service -n 80 --no-pager || true
echo "BRAINK_RUNTIME_SURFACE_HOST_ACTIVATION=FAIL" >&2
exit 9
