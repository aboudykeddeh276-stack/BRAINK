#!/usr/bin/env bash
set -euo pipefail

MODE="${BRAINK_HOST_NETWORK_MODE:-validate}"
APPLY_SYSCTL="${BRAINK_APPLY_SYSCTL:-0}"
APPLY_FIREWALL="${BRAINK_APPLY_FIREWALL:-0}"
ALLOW_INBOUND_STRATUM="${BRAINK_ALLOW_INBOUND_STRATUM:-0}"
PRIVATE_CIDR="${BRAINK_PRIVATE_CIDR:-127.0.0.1/32}"

have() { command -v "$1" >/dev/null 2>&1; }
need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ROOT_REQUIRED:$1" >&2
    exit 20
  fi
}

printf 'BRAINK host network mode: %s\n' "$MODE"
printf 'Private CIDR: %s\n' "$PRIVATE_CIDR"

# Validate expected local port ranges before any mutation.
python - <<'PY'
from braink_runtime.mining_orchestration import validate_port_matrix
r = validate_port_matrix()
print(r)
if r["status"] != "PASS":
    raise SystemExit(10)
PY

if [ "$MODE" = "validate" ]; then
  echo 'HOST_NETWORK_PROFILE_VALIDATED_NO_MUTATION'
  exit 0
fi

if [ "$MODE" != "apply" ]; then
  echo "INVALID_BRAINK_HOST_NETWORK_MODE:$MODE" >&2
  exit 11
fi

if [ "$APPLY_SYSCTL" = "1" ]; then
  need_root sysctl
  cat >/etc/sysctl.d/99-braink-mining-core.conf <<'EOF'
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 262144
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.ip_local_port_range = 1024 65535
EOF
  sysctl --system >/tmp/braink-sysctl-apply.log
  sysctl -n net.core.somaxconn
fi

if [ "$APPLY_FIREWALL" = "1" ]; then
  need_root firewall
  if have ufw; then
    # RPC / IPC / MUX / CDP are private-control surfaces by default.
    ufw allow from "$PRIVATE_CIDR" to any port 8332:8347 proto tcp comment 'BRAINK RPC blades'
    ufw allow from "$PRIVATE_CIDR" to any port 9001:9016 proto tcp comment 'BRAINK ANGM IPC'
    ufw allow from "$PRIVATE_CIDR" to any port 8799:8814 proto tcp comment 'BRAINK MUX'
    ufw allow from "$PRIVATE_CIDR" to any port 9222:9237 proto tcp comment 'BRAINK CDP debug'
    # Pool mining normally uses outbound connections. Only expose local Stratum
    # listeners when the operator explicitly declares this host a proxy/agent.
    if [ "$ALLOW_INBOUND_STRATUM" = "1" ]; then
      ufw allow from "$PRIVATE_CIDR" to any port 3333:3348 proto tcp comment 'BRAINK local Stratum proxy'
    fi
    ufw reload
  else
    echo 'UFW_NOT_AVAILABLE_FIREWALL_NOT_MUTATED' >&2
    exit 21
  fi
fi

echo 'HOST_NETWORK_PROFILE_APPLIED'
