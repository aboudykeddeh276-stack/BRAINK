from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

from enterprise.market.connector_projection_adapter_r8 import project_external_connector
from enterprise.market.connector_service_registry_r25 import registry as connector_registry
from enterprise.orchestration.committed_projection_bridge_r8 import (
    AuthorityClass,
    CallableProjectionAdapter,
    CommittedProjectionBridge,
    ProjectionEnvelope,
    ProjectionReceiptLedger,
    ProjectionSigner,
    Surface,
)
from mcp.braink_process_adapter.backend import BrainkProcessBackend

ROOT = Path(__file__).resolve().parents[2]
KEY = bytes.fromhex("33" * 32)
EVENT = "a" * 64
DOMAIN = "b" * 64


def function_calls(function: ast.FunctionDef) -> set[str]:
    calls: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            calls.add(target.id)
        elif isinstance(target, ast.Attribute):
            parts: list[str] = []
            current = target
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            calls.add(".".join(reversed(parts)))
    return calls


def test_core_projection_bridge() -> None:
    with tempfile.TemporaryDirectory(prefix="r8-projection-core-") as tmp:
        signer = ProjectionSigner(KEY)
        ledger = ProjectionReceiptLedger(Path(tmp) / "projection.sqlite")
        bridge = CommittedProjectionBridge(signer, ledger)

        envelope = signer.create(
            event_hash=EVENT,
            domain_root=DOMAIN,
            sequence=1,
            projection_id="projection://internal/1",
            surface=Surface.ADAPTER,
            target="adapter://internal",
            authority_class=AuthorityClass.INTERNAL,
            operation="APPLY",
            payload={"value": 1},
        )
        calls: list[str] = []
        adapter = CallableProjectionAdapter(
            adapter_id="INTERNAL_FIXTURE",
            surface=Surface.ADAPTER,
            apply_fn=lambda item: {
                "source_event_hash": item.event_hash,
                "producer_truth_hash": item.producer_truth_hash,
                "state": calls.append(item.event_hash) or "APPLIED",
            },
            readback_fn=lambda item, result: {**result, "readback": "PASS"},
            mutating=True,
            readback_required=True,
        )
        first = bridge.project(envelope, adapter)
        second = bridge.project(envelope, adapter)
        assert first["status"] == "RECONCILED"
        assert second["status"] == "REPLAYED_RECONCILED"
        assert calls == [EVENT]
        assert ledger.debt() == []
        assert ledger.verify_chain()["ok"] is True

        failing = signer.create(
            event_hash="c" * 64,
            domain_root=DOMAIN,
            sequence=2,
            projection_id="projection://host/2",
            surface=Surface.PLUGIN,
            target="plugin://fixture",
            authority_class=AuthorityClass.HOST_CONTROLLED,
            operation="APPLY",
            payload={"value": 2},
        )
        state = {"fail": True}
        plugin = CallableProjectionAdapter(
            adapter_id="PLUGIN_FIXTURE",
            surface=Surface.PLUGIN,
            apply_fn=lambda item: (_ for _ in ()).throw(RuntimeError("PLUGIN_DOWN")) if state["fail"] else {
                "source_event_hash": item.event_hash,
                "producer_truth_hash": item.producer_truth_hash,
                "state": "APPLIED",
            },
            readback_fn=lambda item, result: {**result, "readback": "PASS"},
            mutating=True,
            readback_required=True,
        )
        failed = bridge.project(failing, plugin)
        assert failed["status"] == "RECONCILIATION_REQUIRED"
        assert len(ledger.debt()) == 1
        state["fail"] = False
        repaired = bridge.project(failing, plugin)
        assert repaired["status"] == "RECONCILED"
        assert ledger.debt() == []


def test_actual_mcp_backend_projection_path() -> None:
    with tempfile.TemporaryDirectory(prefix="r8-mcp-projection-") as tmp:
        backend = BrainkProcessBackend(state_dir=Path(tmp) / "runtime", key=KEY)
        lease = backend.acquire_lease("WORK-R8-MCP", "projection-agent", requested_epoch=1)
        assert lease["epoch"] == 1

        signer = ProjectionSigner(KEY)
        envelope = signer.create(
            event_hash=EVENT,
            domain_root=DOMAIN,
            sequence=1,
            projection_id="projection://mcp/domain-provision",
            surface=Surface.MCP,
            target="mcp://braink/domain.provision",
            authority_class=AuthorityClass.INTERNAL,
            operation="mcp.capability.invoke",
            payload={
                "capability_id": "domain.provision",
                "context": {
                    "work_id": "WORK-R8-MCP",
                    "actor_id": "projection-agent",
                    "lease_epoch": 1,
                    "scopes": ["domain:write"],
                },
                "payload": {
                    "tx_id": "TX-R8-MCP",
                    "domain": "r8-projection.keddeh",
                    "ip": "127.0.0.1",
                },
                "idempotency_key": "projection-domain-1",
            },
        )
        result = backend.apply_committed_projection(asdict_projection(envelope))
        assert result["status"] == "RECONCILED"
        observed = backend.observe_domain_authority("r8-projection.keddeh")
        assert observed and observed["domain"] == "r8-projection.keddeh"

        replay = backend.apply_committed_projection(asdict_projection(envelope))
        assert replay["status"] == "REPLAYED_RECONCILED"
        assert backend.verify_projection_receipts()["ok"] is True
        assert backend.projection_reconciliation_debt() == []


def asdict_projection(envelope: ProjectionEnvelope) -> dict:
    return {
        "schema_version": envelope.schema_version,
        "event_hash": envelope.event_hash,
        "domain_root": envelope.domain_root,
        "sequence": envelope.sequence,
        "phase": envelope.phase,
        "projection_id": envelope.projection_id,
        "surface": envelope.surface,
        "target": envelope.target,
        "authority_class": envelope.authority_class,
        "operation": envelope.operation,
        "producer_truth_hash": envelope.producer_truth_hash,
        "payload": dict(envelope.payload),
        "authority_evidence": dict(envelope.authority_evidence),
        "source_receipt_hash": envelope.source_receipt_hash,
        "signature": envelope.signature,
    }


def test_connector_projection_path() -> None:
    bindings = connector_registry()
    assert bindings
    for service, row in bindings.items():
        assert row["authority_class"] == "EXTERNALLY_DELEGATED", service
        assert row["readback_required"] is True, service
        assert row["projection_only"] is True, service

    with tempfile.TemporaryDirectory(prefix="r8-connector-") as tmp:
        signer = ProjectionSigner(KEY)
        envelope = signer.create(
            event_hash=EVENT,
            domain_root=DOMAIN,
            sequence=1,
            projection_id="projection://connector/github",
            surface=Surface.CONNECTOR,
            target="connector://github",
            authority_class=AuthorityClass.EXTERNALLY_DELEGATED,
            operation="connector.execute",
            payload={
                "capability": "update_file",
                "path": "docs/example.txt",
                "content": "projection",
            },
            authority_evidence={
                "delegation_id": "connector://github/authenticated",
                "observed": True,
            },
        )
        executed: list[tuple[str, str]] = []

        result = project_external_connector(
            envelope=asdict_projection(envelope),
            service="github",
            key=KEY,
            ledger_path=Path(tmp) / "connector.sqlite",
            execute=lambda service, capability, payload: (
                executed.append((service, capability))
                or {"status": "MUTATED", "path": payload["path"]}
            ),
            readback=lambda service, capability, result: {
                "status": "READBACK_OK",
                "path": result["provider_result"]["path"],
            },
        )
        assert result["status"] == "RECONCILED"
        assert executed == [("github", "update_file")]


def test_sites_mcp_fences_direct_mutators() -> None:
    path = ROOT / "plugins/sites/server/mcp_server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert "sites_apply_committed_projection" in functions
    assert "sites_projection_reconciliation_debt" in functions
    for name in {"site_create", "domain_bind", "version_create", "deploy", "estate_import"}:
        assert name in functions
        calls = function_calls(functions[name])
        assert "governed_required" in calls, name

    native_calls = function_calls(functions["native_casepath"])
    assert "governed_required" in native_calls
    apply_calls = function_calls(functions["sites_apply_committed_projection"])
    assert "_projection_bridge" in apply_calls
    assert "ProjectionEnvelope.from_mapping" in apply_calls


def test_runner_control_plane_contains_projection_laws() -> None:
    data = json.loads((ROOT / ".kex/runner-control-plane.json").read_text())
    rules = set(data["acceptance_rule"])
    required = {
        "MUTATING_MCP_PLUGIN_ADAPTER_CONNECTOR_REQUIRES_COMMITTED_DOMAINSTATE",
        "MCP_PLUGIN_ADAPTER_CONNECTOR_CANNOT_REDEFINE_PRODUCER_TRUTH_OR_AUTHORITY",
        "EXTERNALLY_DELEGATED_PROJECTION_REQUIRES_OBSERVED_DELEGATION_AND_READBACK",
        "UNPROVEN_PROJECTION_AUTHORITY_CANNOT_MUTATE",
        "POSTCOMMIT_PROJECTION_FAILURE_ENTERS_RECONCILIATION_DEBT",
        "PROJECTION_REPLAY_IDEMPOTENT_BY_EVENT_AND_PROJECTION_ID",
    }
    assert required <= rules


def main() -> None:
    tests = [
        test_core_projection_bridge,
        test_actual_mcp_backend_projection_path,
        test_connector_projection_path,
        test_sites_mcp_fences_direct_mutators,
        test_runner_control_plane_contains_projection_laws,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"R8_PROJECTION_SURFACE_CONVERGENCE_PASS {len(tests)}/{len(tests)}")


if __name__ == "__main__":
    main()
