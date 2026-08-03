#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox runtime_volume/workplans logs exports
python3 -m compileall src tests
python3 src/keddeh_application_applet_packager.py --root "$ROOT" --emit-receipt
python3 src/keddeh_deployment_maturity_workplan.py --root "$ROOT" --emit-receipt
python3 -m unittest tests.test_deployment_maturity_workplan -v
