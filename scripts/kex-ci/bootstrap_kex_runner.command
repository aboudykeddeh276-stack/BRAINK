#!/usr/bin/env bash
set -euo pipefail

REPO="${KEDDEH_GITHUB_REPO:-aboudykeddeh276-stack/BRAINK}"
RUNNER_NAME="${KEDDEH_RUNNER_NAME:-KEDDEH-KEX-$(hostname -s)}"
RUNNER_ROOT="${KEDDEH_RUNNER_ROOT:-$HOME/.keddeh/actions-runner}"
LABELS="${KEDDEH_RUNNER_LABELS:-kex,runtime-health,braink,v114,v116}"
WORK_DIR="${KEDDEH_RUNNER_WORK_DIR:-_work}"

log(){ printf '[KEX-RUNNER] %s\n' "$*"; }
fail(){ printf '[KEX-RUNNER] ERROR: %s\n' "$*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || fail "gh CLI is required on the host"
command -v curl >/dev/null 2>&1 || fail "curl is required on the host"
command -v tar >/dev/null 2>&1 || fail "tar is required on the host"
gh auth status >/dev/null 2>&1 || fail "gh is not authenticated"

OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS/$ARCH" in
  Darwin/arm64) RUNNER_OS=osx; RUNNER_ARCH=arm64 ;;
  Darwin/x86_64) RUNNER_OS=osx; RUNNER_ARCH=x64 ;;
  Linux/aarch64|Linux/arm64) RUNNER_OS=linux; RUNNER_ARCH=arm64 ;;
  Linux/x86_64) RUNNER_OS=linux; RUNNER_ARCH=x64 ;;
  *) fail "unsupported host $OS/$ARCH" ;;
esac

log "repository=$REPO"
log "runner=$RUNNER_NAME"
log "host=$OS/$ARCH"
log "labels=$LABELS"

# Preserve the existing virtual environment as a host capability rather than recreating it.
VENV=""
for candidate in \
  "${KEDDEH_VENV:-}" \
  "$PWD/.venv" \
  "$PWD/venv" \
  "$HOME/.venv" \
  "$HOME/venv"; do
  [ -n "$candidate" ] || continue
  if [ -x "$candidate/bin/python" ]; then VENV="$candidate"; break; fi
done
if [ -n "$VENV" ]; then
  log "resident_venv=$VENV"
  "$VENV/bin/python" --version
else
  log "resident_venv=not-found; workflows retain system-python fallback"
fi

mkdir -p "$RUNNER_ROOT"
cd "$RUNNER_ROOT"

# Resolve the current runner release dynamically from GitHub rather than pinning stale binaries.
RUNNER_VERSION="$(gh api repos/actions/runner/releases/latest --jq '.tag_name' | sed 's/^v//')"
[ -n "$RUNNER_VERSION" ] || fail "could not resolve actions/runner release"
ARCHIVE="actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${ARCHIVE}"

if [ ! -x ./config.sh ]; then
  log "installing actions runner $RUNNER_VERSION"
  curl -fL --retry 3 -o "$ARCHIVE" "$URL"
  tar xzf "$ARCHIVE"
  rm -f "$ARCHIVE"
fi

TOKEN="$(gh api --method POST "repos/${REPO}/actions/runners/registration-token" --jq '.token')"
[ -n "$TOKEN" ] || fail "runner registration token was not returned"

# Remove stale local registration before reconfiguration; this never deletes repository state.
if [ -f .runner ]; then
  REMOVE_TOKEN="$(gh api --method POST "repos/${REPO}/actions/runners/remove-token" --jq '.token')"
  ./config.sh remove --token "$REMOVE_TOKEN" >/dev/null 2>&1 || true
fi

./config.sh \
  --unattended \
  --replace \
  --url "https://github.com/${REPO}" \
  --token "$TOKEN" \
  --name "$RUNNER_NAME" \
  --labels "$LABELS" \
  --work "$WORK_DIR"

# Expose resident virtual environment metadata to runner jobs without forcing a new environment.
{
  printf 'KEDDEH_RUNNER_ID=%s\n' "$RUNNER_NAME"
  printf 'KEDDEH_RUNNER_CLASS=self-hosted-kex\n'
  if [ -n "$VENV" ]; then printf 'KEDDEH_VENV=%s\n' "$VENV"; fi
} > .env

if [ -x ./svc.sh ]; then
  log "installing and starting runner service"
  ./svc.sh stop >/dev/null 2>&1 || true
  ./svc.sh uninstall >/dev/null 2>&1 || true
  ./svc.sh install
  ./svc.sh start
  ./svc.sh status || true
else
  fail "runner service script missing after installation"
fi

log "registered and started $RUNNER_NAME"
log "GitHub labels: self-hosted,$LABELS"
