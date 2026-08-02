from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_agent_runtime_service import AgentRuntimeService


def test_acceptance_harness_can_write_receipt_and_readback() -> None:
    service = AgentRuntimeService(ROOT)
    receipt = service.execute_work_order(
        "acceptance_harness_agent",
        "write_receipt",
        "agent_registry_service",
        {"test": "acceptance"},
    )
    assert receipt.authorized is True
    assert receipt.executed is True
    assert Path(receipt.receipt_path).exists()
    assert Path(receipt.outbox_manifest).exists()


def test_codex_cannot_self_promote_local_pass() -> None:
    service = AgentRuntimeService(ROOT)
    receipt = service.execute_work_order(
        "codex_implementation_agent",
        "promote_local_pass",
        "agent_static_guard",
        {"attempt": "self_promote"},
    )
    assert receipt.authorized is False
    assert receipt.executed is False
    assert receipt.reason in {"action_explicitly_denied", "action_not_allowed", "promotion_reserved_for_acceptance_harness"}


def test_virtual_gpu_cannot_render_as_proof() -> None:
    service = AgentRuntimeService(ROOT)
    receipt = service.execute_work_order(
        "virtual_gpu_projection_agent",
        "promote_local_pass",
        "virtual_gpu_hci_dashboard",
        {"attempt": "render_as_proof"},
    )
    assert receipt.authorized is False
    assert receipt.executed is False


def test_virtual_cpu_can_execute_bound_service_contract() -> None:
    service = AgentRuntimeService(ROOT)
    receipt = service.execute_work_order(
        "virtual_cpu_executor",
        "execute_service_contract",
        "hyper_explicit_mesh_runtime",
        {"path": "unit"},
    )
    assert receipt.authorized is True
    assert receipt.executed is True
    assert receipt.result["service_known"] is True


def test_unknown_agent_fails_closed() -> None:
    service = AgentRuntimeService(ROOT)
    receipt = service.execute_work_order(
        "unknown_agent",
        "write_receipt",
        "agent_registry_service",
        {},
    )
    assert receipt.authorized is False
    assert receipt.executed is False
    assert "unknown agent_id" in receipt.reason
