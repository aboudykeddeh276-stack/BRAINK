from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_agent_registry as registry


def test_agent_registry_contains_required_fields_and_abstractions() -> None:
    data = registry.load_registry(ROOT)
    assert data["registry_id"] == "keddeh_agent_registry"
    assert "identity_registry" in data["real_world_abstractions"]
    assert "service_discovery" in data["real_world_abstractions"]
    assert "observability_instrumentation" in data["real_world_abstractions"]
    assert "finite_state_machine" in data["real_world_abstractions"]
    assert len(data["required_agent_fields"]) >= 10


def test_only_acceptance_harness_has_promotion_authority() -> None:
    rows = registry.evaluate_registry(ROOT)
    promotable = [row.agent_id for row in rows if row.promotion_authority]
    assert promotable == ["acceptance_harness_agent"]
    assert all(row.valid for row in rows)


def test_virtual_gpu_and_telemetry_do_not_promote_correctness() -> None:
    data = registry.load_registry(ROOT)
    rules = data["promotion_rules"]
    assert rules["telemetry_may_observe_not_promote"] is True
    assert rules["virtual_gpu_may_render_not_promote"] is True
    gpu = next(agent for agent in data["agent_types"] if agent["agent_id"] == "virtual_gpu_projection_agent")
    assert gpu["promotion_authority"] is False
    assert "substitute_ui_for_test_evidence" in gpu["denied_actions"]


def test_agent_registry_execution_writes_receipt_readback_and_handoff() -> None:
    final = registry.run_agent_registry(ROOT, emit_receipt=True)
    assert final["status"] == "LOCAL_PASS"
    assert final["ledger_readback"] is True
    assert final["hash_used_as_functional_proof"] is False
    assert final["telemetry_promotes_correctness"] is False
    assert final["virtual_gpu_promotes_correctness"] is False
    outbox = Path(final["outbox_manifest"])
    assert outbox.exists()
    receipt = ROOT / "evidence" / "agent_registry_receipt.json"
    assert receipt.exists()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["registry_id"] == "keddeh_agent_registry"
