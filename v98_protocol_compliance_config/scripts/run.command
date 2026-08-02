#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox logs exports
python3 -m compileall src tests
python3 src/keddeh_target_host_receipts.py --root "$ROOT" --emit-receipt
python3 src/keddeh_v98_acceptance_harness.py --root "$ROOT" --emit-receipt
python3 src/keddeh_mesh_scheduler.py --root "$ROOT" --emit-receipt
python3 src/keddeh_mirror_update_lane.py --root "$ROOT" --emit-receipt
python3 src/keddeh_agent_registry.py --root "$ROOT" --emit-receipt
python3 src/keddeh_agent_runtime_service.py --root "$ROOT" --agent-id acceptance_harness_agent --action write_receipt --service-id agent_registry_service --payload-json '{"run_command":"true"}' --emit-receipt
python3 -m unittest discover -s tests -v
