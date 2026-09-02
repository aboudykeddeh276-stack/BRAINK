from __future__ import annotations

from pathlib import Path
import tempfile

from deployment.r23_owner_host_runtime import R23OwnerHostRuntime, free_port


with tempfile.TemporaryDirectory(prefix="braink-r23-owner-host-") as td:
    state = Path(td) / "r23-state.json"
    runtime = R23OwnerHostRuntime(state, port=free_port())
    try:
        started = runtime.start()
        assert started.status == "EXECUTED"
        assert started.health["status"] == "PASS"
        assert started.health["runtime"] == "BRAINK_R23"
        assert runtime.process.alive()

        create = runtime.operate(
            "customer.lifecycle.create",
            {"file_id": "customer-file://owner-host-test", "customer_id": "customer://owner-host-test", "consent": {"privacy": True}},
        )
        assert create["status"] == "EXECUTED"
        transition = runtime.operate(
            "customer.lifecycle.transition",
            {"file_id": "customer-file://owner-host-test", "target": "ACTIVE", "reason": "owner-host activation invariant"},
        )
        assert transition["status"] == "EXECUTED"

        observed = runtime.readback()
        before_root = observed.state["state_root"]
        before_generation = observed.state["generation"]
        assert observed.state["customer_files"]["customer-file://owner-host-test"]["state"] == "ACTIVE"

        rehydrated = runtime.restart_and_rehydrate()
        assert rehydrated.health["status"] == "PASS"
        assert rehydrated.state["state_root"] == before_root
        assert rehydrated.state["generation"] == before_generation
        assert rehydrated.state["customer_files"]["customer-file://owner-host-test"]["state"] == "ACTIVE"
    finally:
        runtime.stop()
        assert not runtime.process.alive()

try:
    R23OwnerHostRuntime(Path(tempfile.gettempdir()) / "forbidden-r23.json", host="0.0.0.0", port=free_port())
    raise AssertionError("non-loopback binding was not rejected")
except ValueError as exc:
    assert str(exc) == "R23_OWNER_HOST_BINDING_REQUIRES_LOOPBACK"

print("R23_OWNER_HOST_RUNTIME_PASS")
