#!/usr/bin/env bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.keddeh.service-spine.plist"
if [[ -f "$PLIST" ]]; then
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  echo "KEDDEH_V98_LAUNCHD_STOP: UNLOADED"
else
  echo "KEDDEH_V98_LAUNCHD_STOP: NO_PLIST"
fi
