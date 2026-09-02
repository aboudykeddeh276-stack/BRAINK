from __future__ import annotations

from pathlib import Path
import json
import tempfile

from deployment.r23_owner_host_runtime import R23OwnerHostRuntime, free_port


with tempfile.TemporaryDirectory(prefix="braink-r23-privacy-boundary-") as td:
    state = Path(td) / "r23-state.json"
    runtime = R23OwnerHostRuntime(state, port=free_port())
    try:
        started = runtime.start()
        assert started.health["status"] == "PASS"

        created = runtime.operate(
            "customer.lifecycle.create",
            {
                "file_id": "customer-file://privacy-boundary",
                "customer_id": "customer://privacy-boundary",
                "consent": {"privacy": True},
            },
        )
        assert created["status"] == "EXECUTED"

        # Bind a real access session through the resident HTTP portal mechanic so the
        # durable store contains identity/session material that must never leak via
        # the generic state readback surface.
        bind = runtime._json(
            "POST",
            "/portal/session/bind",
            {
                "session_token": "SECRET-BEARER-MUST-NOT-LEAK",
                "profile": {"sub": "privacy-subject", "email": "private@example.invalid"},
                "customer_id": "customer://privacy-boundary",
            },
        )
        assert bind["status"] == "EXECUTED"

        local = runtime.readback().state
        assert "customer-file://privacy-boundary" in local["customer_files"]
        assert local["customer_sessions"]

        public = runtime.public_state_summary()
        assert public["status"] == "PASS"
        assert public["detail"] == "REDACTED_INTERNAL_STATE"
        for forbidden in ("customer_files", "customer_sessions", "customer_access_audit", "receipts", "leases", "research", "publications"):
            assert forbidden not in public
        public_bytes = json.dumps(public, sort_keys=True)
        assert "SECRET-BEARER-MUST-NOT-LEAK" not in public_bytes
        assert "private@example.invalid" not in public_bytes
        assert "privacy-subject" not in public_bytes

        before_root = local["state_root"]
        rehydrated = runtime.restart_and_rehydrate()
        assert rehydrated.state["state_root"] == before_root
        assert "customer-file://privacy-boundary" in rehydrated.state["customer_files"]

        public_after = runtime.public_state_summary()
        assert public_after["detail"] == "REDACTED_INTERNAL_STATE"
        assert "customer_files" not in public_after
        assert public_after["state_root"] == rehydrated.state["state_root"]
    finally:
        runtime.stop()

print("R24_R23_PRIVACY_STATE_BOUNDARY_PASS")
