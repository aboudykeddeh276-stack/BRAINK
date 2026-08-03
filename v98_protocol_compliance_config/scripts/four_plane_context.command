#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox runtime_volume/workplans exports
python3 -m compileall src tests
python3 src/keddeh_four_plane_context_framework.py --root "$ROOT" --emit-receipt
python3 -m unittest tests.test_four_plane_context_framework -v
