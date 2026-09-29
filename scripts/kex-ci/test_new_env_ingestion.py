from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))

from mcp.braink_process_adapter.backend import BrainkProcessBackend
from runtime.runtime_route_registry import RuntimeRouteRegistry


def require(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    os.environ["BRAINK_MCP_HMAC_KEY_HEX"] = "4b" * 32
    with tempfile.TemporaryDirectory(prefix="braink-new-env-") as tmp:
        tmp_path = Path(tmp)
        new_env = tmp_path / "NEW-ENV-APP"
        (new_env / "mcp").mkdir(parents=True)
        (new_env / "mcp" / "runtime-manifest.json").write_text(json.dumps({
            "schema": "kex.braink.mcp.runtime.v1",
            "runtime_id": "NEW_ENV_TEST",
            "integration": {"mcp": True, "repository_authority": "source"}
        }))
        (new_env / "mcp" / "server.mjs").write_text(
            "const a=process.argv.slice(2);"
            "if(a[0]!=='--invoke')process.exit(3);"
            "const p=a[2]?JSON.parse(a[2]):{};"
            "console.log(JSON.stringify({status:'PASS',tool:a[1],payload:p}));"
        )
        os.environ["NEW_ENV_APP_ROOT"] = str(new_env)

        route = RuntimeRouteRegistry(ROOT).resolve("new-env-app-mcp")
        require(route["runtime_id"] == "runtime://new-env-app/mcp", "runtime route id mismatch")
        require(route["runtime_class"] == "MCP_STDIO", "runtime class mismatch")

        backend = BrainkProcessBackend(state_dir=tmp_path / "state")
        work_id = "WORK-NEW-ENV-INGEST"
        holder = "agent://test/new-env"
        lease = backend.acquire_lease(work_id, holder)
        context = {
            "work_id": work_id,
            "actor_id": holder,
            "lease_epoch": lease["epoch"],
            "scopes": ["new-env:read", "new-env:network-read", "new-env:execute"],
        }

        manifest = backend.invoke_capability("new_env.manifest", context, {}, "new-env-manifest")
        require(manifest["status"] == "PASS", "manifest capability failed")
        require(manifest["result"]["runtime_id"] == "NEW_ENV_TEST", "manifest carrier mismatch")

        qualified = backend.invoke_capability(
            "new_env.qualify", context,
            {"construct": "BRAINK", "claim": "entry-point reasoning"},
            "new-env-qualify",
        )
        require(qualified["status"] == "PASS", "qualification capability failed")
        require(qualified["result"]["result"]["tool"] == "qualify_construct", "wrong MCP tool invoked")

        challenge = backend.invoke_capability(
            "new_env.challenge", context,
            {"construct": "KEX"},
            "new-env-challenge",
        )
        require(challenge["status"] == "PASS", "challenge capability failed")

        functions = {row["capability_id"]: row for row in backend.function_manifest()}
        for cid in (
            "new_env.manifest", "new_env.qualify", "new_env.challenge", "new_env.self_test",
            "new_env.tl2_probe", "new_env.tl2_guest_lane", "new_env.moebius_contract"
        ):
            require(cid in functions, f"typed function missing: {cid}")
            require(functions[cid]["invoke_via"] == "braink_invoke_capability", f"governed route missing: {cid}")

        print(json.dumps({
            "schema": "braink.new-env-ingestion.test.v1",
            "status": "PASS",
            "runtime_route": route,
            "capabilities_verified": sorted(cid for cid in functions if cid.startswith("new_env.")),
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
