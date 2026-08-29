#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$ROOT/launchd/com.keddeh.service-spine.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/com.keddeh.service-spine.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs" "$ROOT/evidence" "$ROOT/runtime_volume" "$ROOT/runtime_volume/outbox"
sed "s#__KEDDEH_V98_ROOT__#$ROOT#g" "$PLIST_SRC" > "$PLIST_DST"
plutil -lint "$PLIST_DST"
launchctl unload "$PLIST_DST" >/dev/null 2>&1 || true
launchctl load "$PLIST_DST"
echo "KEDDEH_V98_LAUNCHD_INSTALL: LOADED"
echo "plist=$PLIST_DST"
