#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox logs exports
python3 -m compileall src tests
python3 src/keddeh_task_milestone_monitor.py --root "$ROOT" --emit-receipt
python3 -m unittest tests.test_task_milestone_monitor -v
