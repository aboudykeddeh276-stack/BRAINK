from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from deployment.kex_runtime_service_r40 import CanonicalRuntimeHost
from enterprise.auto_binder import Binding
from enterprise.node_vfs_r40 import NodeVFS


AUTHORITY = "authority://source/local"
CAPABILITIES = ["checkpoint", "process", "readback"]


def correction_command(value=297):
    return {
        "source": "test://r40/correction",
        "data_class": "CORRECTION",
        "payload": {"requested": value},
        "authority": AUTHORITY,
        "capabilities": list(CAPABILITIES),
        "illlm": {"intent": "state.write", "lineage": "A", "key": "r40_value", "value": value},
    }


def workload_command(child_id="B", previous_version=0):
    return {
        "source": f"test://r40/workload/{child_id}",
        "data_class": "WORKLOAD",
        "payload": {"workload": child_id},
        "authority": AUTHORITY,
        "capabilities": list(CAPABILITIES),
        "illlm": {"intent": "computer.instantiate", "lineage": "A", "child_id": child_id},
        "resources": {
            "minimum": {"cpu_units": 1, "memory_bytes": 1048576, "storage_bytes": 1048576},
            "target": {"cpu_units": 1, "memory_bytes": 1048576, "storage_bytes": 1048576},
            "maximum": {"cpu_units": 1, "memory_bytes": 1048576, "storage_bytes": 1048576},
            "priority": 50,
            "latency_class": "STANDARD",
            "persistence_required": True,
        },
        "network_id": f"network://local/{child_id}",
        "server_registration": {
            "server_id": f"server://local/{child_id}",
            "endpoint": f"local://{child_id}",
            "capabilities": ["process", "readback"],
            "health": "READY",
        },
        "subscriptions": ["WORKLOAD"],
        "global_delta": {
            "previous_version": previous_version,
            "relation_delta": {"set": {f"node/{child_id}": {"state": "ACTIVE_CANDIDATE"}}},
        },
    }


@pytest.fixture
def host(tmp_path):
    return CanonicalRuntimeHost(tmp_path / "state", "A")


def test_valid_correction_uses_existing_node_and_emits_receipt(host):
    out = host.canonical_execute(correction_command())
    assert out["status"] in {"EXECUTED_DISTRIBUTED_REGISTERED", "EXECUTED_LOCAL_VERIFIED"}
    assert out["readback"]["state"]["r40_value"] == 297
    assert out["readback"]["ledger_verified"] is True
    assert "CLASSIFIED" in out["stages"] and "EXISTING_NODE_RESOLVED" in out["stages"]
    receipts = out["readback"]["memory"]["canonical_correction_receipts"]
    assert out["observation"]["command_root"] in receipts


def test_invalid_data_class_is_blocked_before_execution(host):
    cmd = correction_command(); cmd["data_class"] = "ALIEN"
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:DATA_CLASS"
    assert "RUNTIME_EXECUTED" not in out["stages"]


def test_malformed_command_is_blocked(host):
    out = host.canonical.execute("not-an-object")
    assert out["status"] == "BLOCKED:MALFORMED_COMMAND"


def test_unknown_authority_is_blocked(host):
    cmd = correction_command(); cmd["authority"] = "authority://invented/not-resident"
    out = host.canonical_execute(cmd)
    assert out["status"].startswith("BLOCKED:AUTHORITY_UNRESOLVED:")


def test_unknown_capability_is_blocked(host):
    cmd = correction_command(); cmd["capabilities"] = ["definitely_not_resident"]
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:UNKNOWN_CAPABILITY:definitely_not_resident"


def test_missing_capability_manifest_is_blocked(host):
    cmd = correction_command(); cmd["capabilities"] = []
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:CAPABILITY_MANIFEST_REQUIRED"


def test_illlm_resolution_failure_is_blocked(host):
    cmd = correction_command(); cmd["illlm"]["intent"] = "invented.intent"
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:IL_LLM_RESOLUTION"


def test_braink_operator_unknown_agent_is_denied(host):
    cmd = correction_command()
    cmd["operator"] = {"agent_id": "agent://unknown", "required_scope": "CANONICAL_EXECUTION"}
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:BRAINK_OPERATOR_AUTHORITY"


def test_braink_operator_resident_authority_allows_registered_agent(host):
    reg = host.canonical.register_operator("agent://r40/test")
    epoch = reg["result"]["epoch"]
    cmd = correction_command(298)
    cmd["operator"] = {"agent_id": "agent://r40/test", "required_scope": "CANONICAL_EXECUTION", "expected_epoch": epoch}
    out = host.canonical_execute(cmd)
    assert out["operator_authority"]["decision"] == "ALLOW"
    assert out["readback"]["state"]["r40_value"] == 298


def test_new_node_requires_node_eligible_data_class(host):
    cmd = correction_command(); cmd["illlm"] = {"intent": "computer.instantiate", "lineage": "A", "child_id": "B"}
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:DATA_CLASS_NOT_NODE_ELIGIBLE"
    with pytest.raises(Exception): host.resolve("A/B")


def test_complete_node_promotion_has_no_state_jump(host):
    out = host.canonical_execute(workload_command("B", 0))
    assert out["status"] == "ACTIVE"
    assert out["promotion"] == [
        "CLASSIFIED", "VALIDATED", "MATERIALIZED", "TEMPLATE_BOUND", "AGENT_BOUND", "VFS_BOUND", "NETWORK_BOUND",
        "RUNTIME_CONSTRUCTED", "RUNTIME_RUNNING", "LOCAL_VERIFIED", "MESH_REGISTERED",
        "SERVER_REGISTERED", "SUBSCRIBED", "IL_LLM_REGISTERED", "ACTIVE",
    ]
    assert out["readback"]["ledger_verified"] is True
    assert out["mesh_state"]["status"] == "MESH_REGISTERED"
    assert out["server_state"]["status"] == "SERVER_REGISTERED"
    assert out["subscription_state"]["status"] == "SUBSCRIBED"
    assert out["global_delta"]["status"] == "COMMITTED"
    template_identity = out["readback"]["identity"]["template_identity"]
    assert template_identity["template_id"] == "TPL_KEX_RECURSIVE_COMPUTER_R26"
    assert template_identity["observer_relation_id"] == "OBSERVER2://BRAINK/R26/A/B"
    assert out["node_template"]["identity"] == template_identity


def test_final_mesh_readback_matches_final_runtime_state_root(host):
    out = host.canonical_execute(workload_command("B", 0))
    assert out["status"] == "ACTIVE"
    fabric = host.fabric_node.computer.readback()["memory"]["fabric_local_nodes"]["B"]
    assert fabric["state_root"] == out["readback"]["state_root"]


def test_duplicate_node_is_routed_to_existing_node(host):
    first = host.canonical_execute(workload_command("B", 0)); assert first["status"] == "ACTIVE"
    second = host.canonical_execute(workload_command("B", 1))
    assert second["status"] == "ROUTED_EXISTING_NODE"
    assert host.snapshot(host.resolve("A/B"))["lineage"] == ["A", "B"]


def test_duplicate_correction_is_idempotent(host):
    cmd = correction_command(301)
    first = host.canonical_execute(copy.deepcopy(cmd)); assert first["readback"]["state"]["r40_value"] == 301
    second = host.canonical_execute(copy.deepcopy(cmd))
    assert second["status"] == "DUPLICATE_CORRECTION"
    assert second["readback"]["state"]["r40_value"] == 301


def test_concurrent_duplicate_correction_has_one_effective_execution(host):
    cmd = correction_command(302)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: host.canonical_execute(copy.deepcopy(cmd)), range(4)))
    statuses = [item["status"] for item in results]
    assert statuses.count("DUPLICATE_CORRECTION") == 3
    assert sum(s in {"EXECUTED_DISTRIBUTED_REGISTERED", "EXECUTED_LOCAL_VERIFIED"} for s in statuses) == 1
    assert host.snapshot()["state"]["r40_value"] == 302


def test_vfs_allocation_and_collision_detection(host):
    out = host.canonical_execute(workload_command("B", 0)); assert out["status"] == "ACTIVE"
    child = host.resolve("A/B")
    vfs = NodeVFS(child.runtime, child.state_root / "node-vfs")
    written = vfs.write("B", "proof.json", {"x": 1})
    read = vfs.read("B", "proof.json")
    assert written["logical"] == "vfs://node/B/proof.json"
    assert read["result"]["value"] == {"x": 1}
    existing = child.runtime.binder.bindings[written["logical"]]
    child.runtime.binder.bindings[written["logical"]] = Binding(
        existing.logical, "file:///different-backing.json", existing.adapter_id, existing.aperture, existing.bound_ns
    )
    with pytest.raises(RuntimeError, match="VFS_COLLISION"):
        vfs.write("B", "proof.json", {"x": 2})


def test_mesh_admission_failure_prevents_active_promotion(host, monkeypatch):
    monkeypatch.setattr(host.fabric_admission, "register_local_node", lambda **_: {"status": "BLOCKED:REACHABILITY_UNVERIFIED"})
    out = host.canonical_execute(workload_command("B", 0))
    assert out["status"] == "BLOCKED:REACHABILITY_UNVERIFIED"
    assert "MESH_REGISTERED" not in out["promotion"] and "ACTIVE" not in out["promotion"]


def test_server_registration_failure_prevents_active_promotion(host):
    cmd = workload_command("B", 0); cmd["server_registration"]["health"] = "NOT_READY"
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:SERVER_NOT_READY"
    assert "MESH_REGISTERED" in out["promotion"]
    assert "SERVER_REGISTERED" not in out["promotion"] and "ACTIVE" not in out["promotion"]


def test_subscription_failure_prevents_active_promotion(host):
    cmd = workload_command("B", 0); cmd["subscriptions"] = []
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:SUBSCRIPTIONS_REQUIRED"
    assert "SERVER_REGISTERED" in out["promotion"]
    assert "SUBSCRIBED" not in out["promotion"] and "ACTIVE" not in out["promotion"]


def test_partial_persistence_survives_restart_without_false_active(tmp_path):
    state = tmp_path / "state"
    host1 = CanonicalRuntimeHost(state, "A")
    cmd = workload_command("B", 0); cmd["server_registration"]["health"] = "NOT_READY"
    out = host1.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:SERVER_NOT_READY"
    assert host1.resolve("A/B").ledger.verify()
    host2 = CanonicalRuntimeHost(state, "A")
    restored = host2.snapshot(host2.resolve("A/B"))
    assert restored["ledger_verified"] is True
    assert restored["memory"]["data_class"]["data_class"] == "WORKLOAD"
    assert "B" in host2.canonical.scheduler.snapshot()["allocations"]


def test_restart_after_commit_recovers_node_fabric_global_and_scheduler(tmp_path):
    state = tmp_path / "state"
    host1 = CanonicalRuntimeHost(state, "A")
    out = host1.canonical_execute(workload_command("B", 0)); assert out["status"] == "ACTIVE"
    host2 = CanonicalRuntimeHost(state, "A")
    child = host2.snapshot(host2.resolve("A/B"))
    assert child["ledger_verified"] is True
    assert host2.canonical.global_knowledge.snapshot()["version"] == 1
    assert "B" in host2.canonical.scheduler.snapshot()["allocations"]
    fabric_memory = host2.fabric_node.computer.readback()["memory"]
    assert "B" in fabric_memory["fabric_local_nodes"]
    assert fabric_memory["node_subscriptions"]["B"] == ["WORKLOAD"]
    assert "server://local/B" in fabric_memory["server_bindings"]


def test_global_version_conflict_is_rejected(host):
    first = host.canonical_execute(workload_command("B", 0)); assert first["status"] == "ACTIVE"
    cmd = correction_command(303)
    cmd["global_delta"] = {"previous_version": 0, "relation_delta": {"set": {"late": True}}}
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:GLOBAL_IL_LLM_DELTA"
    assert "STALE_GLOBAL_VERSION" in out["detail"]


def test_execution_failure_is_not_promoted(host, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("INJECTED_BRAINK_EXECUTION_FAILURE")
    monkeypatch.setattr(host.canonical.illlm, "execute", fail)
    out = host.canonical_execute(correction_command(304))
    assert out["status"] in {"BLOCKED:RUNTIME_EXECUTION", "FAILED:RUNTIME_EXECUTION"}
    assert "LOCAL_VERIFIED" not in out.get("stages", [])


def test_ledger_failure_blocks_local_verification(host, monkeypatch):
    monkeypatch.setattr(host.computer.ledger, "verify", lambda: False)
    out = host.canonical_execute(correction_command(305))
    assert out["status"] in {"BLOCKED:LOCAL_LEDGER_VERIFICATION", "FAILED:LOCAL_LEDGER_VERIFICATION"}


def test_server_registration_readback_mismatch_is_mechanical_failure(host, monkeypatch):
    original_readback = host.fabric_node.computer.readback
    def stale_readback():
        body = original_readback()
        body["memory"] = dict(body.get("memory", {})); body["memory"]["server_bindings"] = {}
        return body
    monkeypatch.setattr(host.fabric_node.computer, "readback", stale_readback)
    with pytest.raises(RuntimeError, match="SERVER_REGISTRATION_READBACK_FAILED"):
        host.fabric_admission.register_server({"server_id": "server://x", "endpoint": "local://x", "capabilities": ["process"], "health": "READY"})


def test_resource_scheduler_rejects_impossible_minimum(host):
    cmd = workload_command("B", 0)
    cmd["resources"]["minimum"]["cpu_units"] = host.canonical.scheduler.pool.cpu_units + 1
    cmd["resources"]["target"]["cpu_units"] = cmd["resources"]["minimum"]["cpu_units"]
    cmd["resources"]["maximum"]["cpu_units"] = cmd["resources"]["minimum"]["cpu_units"]
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:RESOURCE_SCHEDULER"
    assert "RESOURCE_BLOCKED:cpu_units" in out["detail"]


def test_global_state_corruption_is_detected_on_restart(tmp_path):
    state = tmp_path / "state"
    host1 = CanonicalRuntimeHost(state, "A")
    path = host1.canonical.global_knowledge.path
    body = json.loads(path.read_text()); body["schema"] = "tampered"
    path.write_text(json.dumps(body))
    host2 = CanonicalRuntimeHost(state, "A")
    with pytest.raises(RuntimeError, match="GLOBAL_ILLLM_SCHEMA_MISMATCH"):
        host2.canonical.global_knowledge.snapshot()
