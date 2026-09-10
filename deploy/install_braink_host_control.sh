#!/usr/bin/env bash
set -euo pipefail

RUN_USER="${1:-${SUDO_USER:-}}"
REPO_SRC="${BRAINK_REPO_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
INSTALL_ROOT="${BRAINK_INSTALL_ROOT:-/opt/braink}"
STATE_ROOT="${BRAINK_STATE_ROOT:-/var/lib/braink}"
UNIT_SRC="${REPO_SRC}/deploy/systemd/braink-desktop-commander@.service"
UNIT_DST="/etc/systemd/system/braink-desktop-commander@.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root (sudo)." >&2
  exit 2
fi
if [[ -z "${RUN_USER}" ]]; then
  echo "ERROR: supply the Linux user that owns the Desktop Commander session." >&2
  exit 3
fi
id "${RUN_USER}" >/dev/null 2>&1 || { echo "ERROR: user ${RUN_USER} does not exist" >&2; exit 4; }
command -v python3 >/dev/null || { echo "ERROR: python3 missing" >&2; exit 5; }
command -v node >/dev/null || { echo "ERROR: node missing" >&2; exit 6; }
command -v npm >/dev/null || { echo "ERROR: npm missing" >&2; exit 7; }
command -v npx >/dev/null || { echo "ERROR: npx missing" >&2; exit 8; }
command -v systemctl >/dev/null || { echo "ERROR: systemd missing" >&2; exit 9; }
command -v rsync >/dev/null || { echo "ERROR: rsync missing" >&2; exit 10; }

mkdir -p "${INSTALL_ROOT}" "${STATE_ROOT}/host-control/${RUN_USER}" "${STATE_ROOT}/host-activation"
rsync -a --delete --exclude '.git' "${REPO_SRC}/" "${INSTALL_ROOT}/"
install -m 0644 "${UNIT_SRC}" "${UNIT_DST}"
chown -R "${RUN_USER}:${RUN_USER}" "${STATE_ROOT}/host-control/${RUN_USER}" "${STATE_ROOT}/host-activation"

cd "${INSTALL_ROOT}"
python3 -m py_compile runtime/runtime_registry.py
python3 -m py_compile runtime/host_control/braink_desktop_commander_runtime.py
python3 -m py_compile runtime/host_control/braink_host_fabric.py
python3 -m py_compile runtime/host_control/braink_host_activation.py
python3 -m py_compile runtime/host_control/braink_dc_remote_probe.py
python3 -m runtime.host_control.braink_host_fabric --self-test
python3 -m runtime.host_control.braink_host_activation --self-test
python3 -m runtime.host_control.braink_dc_remote_probe --self-test

systemctl daemon-reload
systemctl enable --now "braink-desktop-commander@${RUN_USER}.service"
sleep 2
systemctl is-active --quiet "braink-desktop-commander@${RUN_USER}.service" || {
  systemctl --no-pager --full status "braink-desktop-commander@${RUN_USER}.service" || true
  echo "ERROR: Desktop Commander carrier service is not active" >&2
  exit 11
}

export BRAINK_HOST_CONTROL_STATE="${STATE_ROOT}/host-control/${RUN_USER}"
export BRAINK_HOST_ACTIVATION_STATE="${STATE_ROOT}/host-activation"
python3 -m runtime.host_control.braink_host_activation --issue-challenge

cat <<EOF
BRAINK_HOST_CONTROL_CARRIER_ACTIVE user=${RUN_USER}
ACTIVATION_CHALLENGE=${STATE_ROOT}/host-activation/challenge.json
ACTIVATION_RESPONSE=${STATE_ROOT}/host-activation/response.json

The Desktop Commander supervisor is active, but HOST_READY is intentionally NOT promoted yet.
The Desktop Commander remote control path must execute this bounded probe on this host:

  python3 ${INSTALL_ROOT}/runtime/host_control/braink_dc_remote_probe.py \
    --challenge ${STATE_ROOT}/host-activation/challenge.json \
    --response ${STATE_ROOT}/host-activation/response.json

That command must be issued THROUGH the Desktop Commander remote/MCP path, not locally by the installer.
The response is operational correlation evidence, not cryptographic carrier attestation.

After that external probe has completed, bind BRAINK_HOST_AUTHORITY_ROOT and execute:

  cd ${INSTALL_ROOT} && \
  BRAINK_HOST_CONTROL_STATE=${STATE_ROOT}/host-control/${RUN_USER} \
  BRAINK_HOST_ACTIVATION_STATE=${STATE_ROOT}/host-activation \
  BRAINK_HOST_AUTHORITY_ROOT=<bound-proof-root> \
  python3 -m runtime.host_control.braink_host_activation --activate
EOF
