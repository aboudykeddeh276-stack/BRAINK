#!/usr/bin/env bash
set -euo pipefail

APP_NAME="BRAINKChatBot"
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="${ROOT}/${APP_NAME}.app"
BIN="${APP}/Contents/MacOS/${APP_NAME}"
PLIST="${APP}/Contents/Info.plist"
RES="${APP}/Contents/Resources"
LOG="${APP}.build.log"

mkdir -p "${APP}/Contents/MacOS" "${RES}" "${ROOT}/build"

cat > "${PLIST}" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>BRAINKChatBot</string>
  <key>CFBundleIdentifier</key><string>systems.kex.braink.chatbot</string>
  <key>CFBundleName</key><string>BRAINKChatBot</string>
  <key>CFBundleDisplayName</key><string>BRAINKChatBot</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

echo "[build] compiling $APP_NAME" | tee "$LOG"
swiftc "${ROOT}/Sources"/*.swift \
  -o "$BIN" \
  -framework SwiftUI \
  -framework AppKit \
  -parse-as-library | tee -a "$LOG"

chmod +x "$BIN"

echo "[build] output: $APP" | tee -a "$LOG"
echo "[build] run: open '$APP'" | tee -a "$LOG"
open "$APP" &> /dev/null || true
