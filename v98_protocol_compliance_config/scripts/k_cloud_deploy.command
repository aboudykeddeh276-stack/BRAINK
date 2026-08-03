#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox logs exports
python3 -m compileall src tests
python3 src/keddeh_k_cloud_adapter.py --root "$ROOT" --emit-receipt
python3 src/keddeh_test_runner.py --root "$ROOT" --emit-receipt
