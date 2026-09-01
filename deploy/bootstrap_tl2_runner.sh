#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${KEX_REPO_URL:-https://github.com/aboudykeddeh276-stack/BRAINK}"
RUNNER_NAME="${KEX_TL2_RUNNER_NAME:-kex-tl2-$(hostname)}"
RUNNER_DIR="${KEX_TL2_RUNNER_DIR:-$HOME/actions-runner-kex-tl2}"
LABELS="${KEX_TL2_RUNNER_LABELS:-kex,tl2}"
TOKEN="${KEX_GITHUB_RUNNER_TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
  echo '{"status":"BLOCKED","reason":"KEX_GITHUB_RUNNER_TOKEN is required","claimBoundary":"Runner registration cannot be claimed without a live one-time GitHub registration token."}'
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo '{"status":"BLOCKED","reason":"curl unavailable"}'
  exit 3
fi

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

if [[ ! -x ./config.sh ]]; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) GH_ARCH="x64" ;;
    aarch64|arm64) GH_ARCH="arm64" ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 4 ;;
  esac
  VERSION="${KEX_GITHUB_RUNNER_VERSION:-}"
  if [[ -z "$VERSION" ]]; then
    VERSION="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"].lstrip("v"))')"
  fi
  PKG="actions-runner-linux-${GH_ARCH}-${VERSION}.tar.gz"
  curl -fL "https://github.com/actions/runner/releases/download/v${VERSION}/${PKG}" -o "$PKG"
  tar xzf "$PKG"
fi

./config.sh --unattended --replace \
  --url "$REPO_URL" \
  --token "$TOKEN" \
  --name "$RUNNER_NAME" \
  --labels "$LABELS" \
  --work "_work"

if [[ "${KEX_TL2_INSTALL_SERVICE:-true}" == "true" && -x ./svc.sh ]]; then
  sudo ./svc.sh install || true
  sudo ./svc.sh start
  SERVICE_MODE="service"
else
  nohup ./run.sh > runner.log 2>&1 &
  SERVICE_MODE="nohup"
fi

python3 - <<'PY'
import json, os
print(json.dumps({
  "status": "REGISTERED_AND_STARTED",
  "runnerName": os.environ.get("KEX_TL2_RUNNER_NAME") or "derived-from-hostname",
  "labels": os.environ.get("KEX_TL2_RUNNER_LABELS", "kex,tl2").split(","),
  "deploymentClass": "TL2_EXECUTOR",
  "claimBoundary": "This receipt proves local runner bootstrap completion only; TL2_LIVE still requires the deployment workflow readback receipt."
}, indent=2))
PY
