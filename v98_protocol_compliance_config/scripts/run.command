#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p evidence runtime_volume runtime_volume/outbox runtime_volume/task_packets logs exports
python3 -m compileall src tests
python3 src/keddeh_target_host_receipts.py --root "$ROOT" --emit-receipt
python3 src/keddeh_dependency_failure_orchestrator.py --root "$ROOT" --emit-receipt
python3 src/keddeh_k_cloud_adapter.py --root "$ROOT" --emit-receipt
python3 src/keddeh_v98_acceptance_harness.py --root "$ROOT" --emit-receipt
python3 src/keddeh_mesh_scheduler.py --root "$ROOT" --emit-receipt
python3 src/keddeh_mirror_update_lane.py --root "$ROOT" --emit-receipt
python3 src/keddeh_agent_registry.py --root "$ROOT" --emit-receipt
python3 src/keddeh_agent_runtime_service.py --root "$ROOT" --agent-id acceptance_harness_agent --action write_receipt --service-id agent_registry_service --payload-json '{"run_command":"true"}' --emit-receipt
python3 src/keddeh_btc_core_protocol_router.py --root "$ROOT" --once --emit-receipt
python3 src/keddeh_task_milestone_monitor.py --root "$ROOT" --emit-receipt
python3 src/keddeh_workflow_schema_guard.py --root "$ROOT" --emit-receipt
python3 src/keddeh_design_deployment_workflow.py --root "$ROOT" --emit-receipt
python3 -m unittest discover -s tests -v
python3 src/keddeh_test_runner.py --root "$ROOT" --emit-receipt
