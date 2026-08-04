#!/bin/bash
set -euo pipefail

REPO_SLUG="${REPO_SLUG:-aboudykeddeh276-stack/BRAINK}"
RUNNER_NAME="${RUNNER_NAME:-KEDDEH-M3-$(scutil --get LocalHostName 2>/dev/null || hostname -s)}"
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner-keddeh-m3}"
RUNNER_LABELS="${RUNNER_LABELS:-KEDDEH-M3}"
WORK_DIR="${WORK_DIR:-_work}"

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
info() { printf '[INFO] %s\n' "$*"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "macOS is required"
[[ "$(uname -m)" == "arm64" ]] || fail "Apple-silicon ARM64 is required"
command -v gh >/dev/null || fail "GitHub CLI (gh) is required"
command -v curl >/dev/null || fail "curl is required"
command -v tar >/dev/null || fail "tar is required"
gh auth status >/dev/null 2>&1 || fail "Run 'gh auth login' with repository Administration write permission"

info "Resolving current GitHub Actions runner application for macOS ARM64"
APP_JSON="$(gh api -H 'Accept: application/vnd.github+json' "/repos/${REPO_SLUG}/actions/runners/downloads")"
read -r DOWNLOAD_URL FILENAME SHA256 < <(python3 - "$APP_JSON" <<'PY'
import json, sys
apps=json.loads(sys.argv[1])
for app in apps:
    if app.get('os') == 'osx' and app.get('architecture') == 'arm64':
        print(app['download_url'], app['filename'], app.get('sha256_checksum',''))
        break
else:
    raise SystemExit('No macOS ARM64 runner application returned by GitHub')
PY
)

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"
if [[ ! -x ./config.sh ]]; then
  info "Downloading ${FILENAME}"
  curl --fail --location --retry 3 --output "$FILENAME" "$DOWNLOAD_URL"
  if [[ -n "$SHA256" ]]; then
    ACTUAL="$(shasum -a 256 "$FILENAME" | awk '{print $1}')"
    [[ "$ACTUAL" == "$SHA256" ]] || fail "Runner checksum mismatch"
  fi
  tar xzf "$FILENAME"
fi

if [[ -f .runner ]]; then
  info "Runner already configured; preserving registration"
else
  info "Minting one-hour repository registration token"
  TOKEN="$(gh api --method POST -H 'Accept: application/vnd.github+json' "/repos/${REPO_SLUG}/actions/runners/registration-token" --jq .token)"
  [[ -n "$TOKEN" ]] || fail "GitHub did not return a registration token"
  ./config.sh --unattended \
    --url "https://github.com/${REPO_SLUG}" \
    --token "$TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" \
    --work "$WORK_DIR" \
    --replace
fi

info "Installing and starting launchd service"
./svc.sh install || true
./svc.sh start
./svc.sh status

info "Verifying runner registration and labels"
gh api -H 'Accept: application/vnd.github+json' "/repos/${REPO_SLUG}/actions/runners" \
  --jq ".runners[] | select(.name == \"${RUNNER_NAME}\") | {name,status,busy,labels:[.labels[].name]}"

cat <<EOF
[PASS] Runner bootstrap complete.
Required workflow labels resolve as:
  self-hosted   automatically assigned by GitHub
  macOS         automatically assigned by GitHub
  ARM64         automatically assigned by GitHub
  KEDDEH-M3     custom label assigned by this script
EOF
