#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume outbox logs exports
python3 -m compileall src tests
python3 src/keddeh_v98_acceptance_harness.py --root "$ROOT" --emit-receipt
python3 -m unittest discover -s tests -v
