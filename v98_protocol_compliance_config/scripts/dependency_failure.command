#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox runtime_volume/task_packets exports logs
python3 -m compileall src tests
python3 src/keddeh_dependency_failure_orchestrator.py --root "$ROOT" --emit-receipt
python3 src/keddeh_test_runner.py --root "$ROOT" --emit-receipt
