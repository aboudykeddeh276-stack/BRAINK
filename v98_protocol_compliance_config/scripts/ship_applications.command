#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence exports runtime_volume runtime_volume/outbox runtime_volume/k_app_packages runtime_volume/application_catalog
python3 -m compileall src tests
python3 src/keddeh_application_applet_packager.py --root "$ROOT" --emit-receipt
python3 -m unittest tests.test_application_applet_packager -v
