from __future__ import annotations

import copy

from deployment.kex_runtime_service_r40 import CanonicalRuntimeHost
from enterprise.node_lease_r40 import NodeLeaseRegistryR40, semantic_root
from enterprise.node_vfs_r40 import NodeVFS


AUTHORITY = "authority://source/local"
CAPABILITIES = ["checkpoint", "process", "readback"]


def manager(host, lineage="A"):
    owner = host.resolve(lineage)
    return owner, NodeLeaseRegistryR40(NodeVFS(owner.runtime, owner.state_root / "node-vfs"), owner.identity.computer_id)


def acquire(registry, current_sequence=0, ttl_events=None):
    return registry.acquire(
        logical_identity="node://A/B",
        target_node_id="B",
        authority=AUTHORITY,
        capabilities=CAPABILITIES,
        current_sequence=current_sequence,
        ttl_events=ttl_events,
    )


def workload_command(child_id="B", previous_version=0, ttl_events=None):
    command = {
        "source": f"test://r40/lease-workload/{child_id}",
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
    if ttl_events is not None:
        command["lease"] = {"ttl_events": ttl_events}
    return command


def child_correction(value=1):
    return {
        "source": "test://r40/lease-child-correction",
        "data_class": "CORRECTION",
        "payload": {"requested": value},
        "authority": AUTHORITY,
        "capabilities": list(CAPABILITIES),
        "illlm": {"intent": "state.write", "lineage": "A/B", "key": "lease_guard_value", "value": value},
    }


def advance_parent_to_sequence(host, sequence):
    owner = host.resolve("A")
    counter = 0
    while len(owner.ledger.events) < int(sequence):
        counter += 1
        host.write_memory("A", "lease_test_clock", counter)
    return len(owner.ledger.events)


def test_lease_acquire_is_cas_backed_and_duplicate_is_blocked(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    owner, registry = manager(host)
    first = acquire(registry, current_sequence=len(owner.ledger.events))
    assert first["status"] == "LEASE_LIVE"
    assert first["lease"]["lifecycle_state"] == "LIVE"
    assert first["lease"]["target_vfs_root"] == "vfs://node/B/"
    second = acquire(registry, current_sequence=len(owner.ledger.events))
    assert second["status"] == "BLOCKED:LEASE_ACTIVE"
    assert second["lease"]["generation"] == 1


def test_wall_clock_observation_is_not_part_of_semantic_lease_identity(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    _, registry = manager(host)
    live = acquire(registry)["lease"]
    changed_observation = copy.deepcopy(live)
    changed_observation["observed_at_ns"] += 10_000_000
    assert semantic_root(live) == semantic_root(changed_observation) == live["semantic_root"]


def test_incremental_gc_requires_expiry_then_quiesce_then_tombstone_then_reclaim(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    _, registry = manager(host)
    live = acquire(registry, current_sequence=10, ttl_events=2)
    assert live["status"] == "LEASE_LIVE"
    assert registry.gc(current_sequence=11, max_scan=1) == []
    step1 = registry.gc(current_sequence=12, max_scan=1)
    assert step1[0]["status"] == "LEASE_QUIESCING"
    step2 = registry.gc(current_sequence=12, max_scan=1)
    assert step2[0]["status"] == "LEASE_TOMBSTONED"
    step3 = registry.gc(current_sequence=12, max_scan=1)
    assert step3[0]["status"] == "LEASE_RECLAIMED"
    reclaimed = registry.read("node://A/B")
    assert reclaimed["backing_disposition"] == "PRESERVE_AUDIT_EVIDENCE"
    reacquired = acquire(registry, current_sequence=13, ttl_events=2)
    assert reacquired["status"] == "LEASE_LIVE"
    assert reacquired["lease"]["generation"] == 2


def test_active_readers_hold_quiescing_lease_before_tombstone(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    _, registry = manager(host)
    live = acquire(registry, current_sequence=0, ttl_events=1)["lease"]
    readers = registry.change_readers(
        "node://A/B",
        delta=1,
        expected_generation=live["generation"],
        current_sequence=0,
    )
    assert readers["lease"]["active_readers"] == 1
    assert registry.gc(current_sequence=1, max_scan=1)[0]["status"] == "LEASE_QUIESCING"
    assert registry.gc(current_sequence=1, max_scan=1) == []
    released = registry.change_readers("node://A/B", delta=-1, expected_generation=live["generation"])
    assert released["lease"]["active_readers"] == 0
    assert registry.gc(current_sequence=1, max_scan=1)[0]["status"] == "LEASE_TOMBSTONED"


def test_expired_live_label_cannot_admit_new_reader_without_gc(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    _, registry = manager(host)
    live = acquire(registry, current_sequence=5, ttl_events=2)["lease"]
    blocked = registry.change_readers(
        "node://A/B",
        delta=1,
        expected_generation=live["generation"],
        current_sequence=7,
    )
    assert blocked["status"] == "BLOCKED:LEASE_EXPIRED"
    assert registry.read("node://A/B")["active_readers"] == 0


def test_stale_generation_cannot_mutate_reacquired_lease(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    _, registry = manager(host)
    first = acquire(registry, current_sequence=0, ttl_events=1)["lease"]
    registry.gc(current_sequence=1, max_scan=1)
    registry.gc(current_sequence=1, max_scan=1)
    registry.gc(current_sequence=1, max_scan=1)
    second = acquire(registry, current_sequence=2, ttl_events=1)["lease"]
    assert second["generation"] == first["generation"] + 1
    stale = registry.change_readers("node://A/B", delta=1, expected_generation=first["generation"], current_sequence=2)
    assert stale["status"] == "BLOCKED:LEASE_STALE_GENERATION"


def test_index_failure_reclaims_allocated_record_instead_of_stranding_it(tmp_path, monkeypatch):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    _, registry = manager(host)
    monkeypatch.setattr(registry, "_index_add", lambda _record: (_ for _ in ()).throw(RuntimeError("INJECTED_INDEX_FAILURE")))
    out = acquire(registry, current_sequence=0, ttl_events=4)
    assert out["status"] == "FAILED:LEASE_INDEX_BIND"
    assert out["rollback"]["status"] == "LEASE_RECLAIMED"
    assert registry.read("node://A/B")["lifecycle_state"] == "RECLAIMED"


def test_lease_survives_host_restart(tmp_path):
    state = tmp_path / "state"
    host1 = CanonicalRuntimeHost(state, "A")
    owner1, registry1 = manager(host1)
    live = acquire(registry1, current_sequence=len(owner1.ledger.events), ttl_events=10)["lease"]
    host2 = CanonicalRuntimeHost(state, "A")
    _, registry2 = manager(host2)
    restored = registry2.read("node://A/B")
    assert restored["semantic_root"] == live["semantic_root"]
    assert restored["lifecycle_state"] == "LIVE"


def test_canonical_materialization_binds_lease_to_parent_and_child(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    out = host.canonical_execute(workload_command("B", 0))
    assert out["status"] == "ACTIVE"
    assert out["lease_state"]["status"] == "LEASE_LIVE"
    assert "RING1_LEASE_ALLOCATED" in out["stages"]
    assert "RING1_LEASE_FINAL_VERIFIED" in out["stages"]
    parent_memory = host.snapshot(host.resolve("A"))["memory"]
    lease = out["lease_state"]["lease"]
    assert parent_memory["canonical_node_leases"][lease["lease_id"]]["semantic_root"] == lease["semantic_root"]
    child_memory = host.snapshot(host.resolve("A/B"))["memory"]
    assert child_memory["allocation_lease"]["lease_id"] == lease["lease_id"]


def test_too_short_lease_cannot_promote_node_active(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    out = host.canonical_execute(workload_command("B", 0, ttl_events=1))
    assert out["status"] == "BLOCKED:LEASE_EXPIRED_BEFORE_ACTIVE"
    assert "ACTIVE" not in out["promotion"]
    _, registry = manager(host)
    assert registry.read("node://A/B")["lifecycle_state"] == "QUIESCING"


def test_scheduler_failure_retires_pre_materialization_lease(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    cmd = workload_command("B", 0)
    impossible = host.canonical.scheduler.pool.cpu_units + 1
    for bound in ("minimum", "target", "maximum"):
        cmd["resources"][bound]["cpu_units"] = impossible
    out = host.canonical_execute(cmd)
    assert out["status"] == "BLOCKED:RESOURCE_SCHEDULER"
    _, registry = manager(host)
    assert registry.read("node://A/B")["lifecycle_state"] == "RECLAIMED"


def test_runtime_failure_retires_lease_and_returns_failed_mechanic(tmp_path, monkeypatch):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    monkeypatch.setattr(host.canonical.illlm, "execute", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("INJECTED")))
    out = host.canonical_execute(workload_command("B", 0))
    assert out["status"] == "FAILED:RUNTIME_EXECUTION"
    _, registry = manager(host)
    assert registry.read("node://A/B")["lifecycle_state"] == "RECLAIMED"


def test_expired_parent_lease_blocks_existing_node_mutation_before_execution(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    out = host.canonical_execute(workload_command("B", 0, ttl_events=2))
    assert out["status"] == "ACTIVE"
    lease = out["lease_state"]["lease"]
    advance_parent_to_sequence(host, lease["expires_sequence"])
    blocked = host.canonical_execute(child_correction(7))
    assert blocked["status"] == "BLOCKED:LEASE_EXPIRED"
    assert host.snapshot(host.resolve("A/B"))["state"].get("lease_guard_value") is None


def test_reclaimed_lease_blocks_existing_node_mutation_without_deleting_node(tmp_path):
    host = CanonicalRuntimeHost(tmp_path / "state", "A")
    out = host.canonical_execute(workload_command("B", 0, ttl_events=2))
    assert out["status"] == "ACTIVE"
    lease = out["lease_state"]["lease"]
    advance_parent_to_sequence(host, lease["expires_sequence"])
    for _ in range(3):
        host.canonical.run_lease_gc("A", max_scan=1)
    _, registry = manager(host)
    assert registry.read("node://A/B")["lifecycle_state"] == "RECLAIMED"
    blocked = host.canonical_execute(child_correction(9))
    assert blocked["status"] == "BLOCKED:LEASE_LOCKED_RECLAIMED"
    assert host.snapshot(host.resolve("A/B"))["ledger_verified"] is True
