from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

REPO_ROOT = Path(os.environ.get("BRAINK_REPO_ROOT", Path(__file__).resolve().parents[1]))
RUNTIME = REPO_ROOT / "runtime"
REPORTS = REPO_ROOT / "reports"

mcp = MCPServer("braink-process-adapter")

ALLOWED_RECEIPTS = {
    "r8_machine_genesis": REPORTS / "architecture-migration-r8.json",
    "r11_global_service_fabric": REPORTS / "braink_global_service_fabric_r11_receipt.json",
    "r12_live_service_fabric": REPORTS / "braink_live_service_fabric_r12_receipt.json",
    "r13_typed_service_fabric": REPORTS / "BRAINK_R13_TYPED_SERVICE_FABRIC_RECEIPT.json",
    "r15_external_path": REPORTS / "BRAINK_R15_EXTERNAL_PATH_RECEIPT.json",
}


def _run(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    cp = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    return {
        "command": cmd,
        "returncode": cp.returncode,
        "stdout": cp.stdout[-12000:],
        "stderr": cp.stderr[-12000:],
        "status": "PASS" if cp.returncode == 0 else "FAIL",
    }


def _require(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"E_RUNTIME_MISSING:{path.relative_to(REPO_ROOT)}")
    return str(path)


@mcp.tool(
    name="braink_capabilities",
    description="Use this when you need the callable BRAINK process surface and the exact runtime files currently present.",
)
def braink_capabilities() -> dict[str, Any]:
    tools = {
        "machine_genesis": RUNTIME / "braink_machine_genesis_r8.js",
        "regenerative_fabric": RUNTIME / "braink_regenerative_fabric_r9_r10.py",
        "global_service_fabric": RUNTIME / "braink_global_service_fabric_r11.py",
        "typed_service_fabric": RUNTIME / "braink_typed_service_fabric_r13.py",
        "external_probe": RUNTIME / "braink_external_probe_r15.sh",
    }
    return {
        "repo_root": str(REPO_ROOT),
        "runtime_presence": {k: v.exists() for k, v in tools.items()},
        "receipt_presence": {k: v.exists() for k, v in ALLOWED_RECEIPTS.items()},
        "storage_contract": "ENCODED_MEDIUM->ZEROLESS_GEOMETRY->CONTROLLER->LOGICAL_OBJECTS->VFS_RESOLVER",
        "vfs_role": "RESOLVER_ONLY",
    }


@mcp.tool(
    name="braink_machine_genesis",
    description="Use this when you need to launch, enter, install BRAINK into, or reboot-verify the R8 machine specimen.",
)
def braink_machine_genesis(action: str) -> dict[str, Any]:
    allowed = {"init", "enter", "install", "boot-verify"}
    if action not in allowed:
        raise ValueError(f"action must be one of {sorted(allowed)}")
    script = _require(RUNTIME / "braink_machine_genesis_r8.js")
    return _run(["node", script, action], timeout=60)


@mcp.tool(
    name="braink_regenerative_fabric",
    description="Use this when you need the R9/R10 descendant-generation, replication, failover, and reconciliation process executed as one verified operation.",
)
def braink_regenerative_fabric() -> dict[str, Any]:
    script = _require(RUNTIME / "braink_regenerative_fabric_r9_r10.py")
    return _run(["python", script], timeout=180)


@mcp.tool(
    name="braink_global_service_fabric",
    description="Use this when you need the resident SERVER/DOMAIN/DNS/REGISTRAR/TLS/CLOUD roots installed, replicated, failed over, and reconciled.",
)
def braink_global_service_fabric() -> dict[str, Any]:
    script = _require(RUNTIME / "braink_global_service_fabric_r11.py")
    return _run(["python", script], timeout=180)


@mcp.tool(
    name="braink_external_probe",
    description="Use this when you need direct public-path evidence for a domain. This tool observes only; it never claims registrar, DNS, or CA mutation authority.",
)
def braink_external_probe(domain: str = "keddeh.com") -> dict[str, Any]:
    if not domain or any(ch.isspace() for ch in domain) or "/" in domain:
        raise ValueError("domain must be a bare DNS name")
    script = _require(RUNTIME / "braink_external_probe_r15.sh")
    out = Path("/tmp") / f"braink-r15-{os.getpid()}.json"
    result = _run(["bash", script, domain, str(out)], timeout=60)
    if out.exists():
        try:
            result["receipt"] = json.loads(out.read_text())
        finally:
            out.unlink(missing_ok=True)
    return result


@mcp.tool(
    name="braink_read_receipt",
    description="Use this when you need an existing BRAINK execution receipt without rerunning a mutating process.",
)
def braink_read_receipt(receipt: str) -> dict[str, Any]:
    if receipt not in ALLOWED_RECEIPTS:
        raise ValueError(f"receipt must be one of {sorted(ALLOWED_RECEIPTS)}")
    path = ALLOWED_RECEIPTS[receipt]
    if not path.exists():
        return {"status": "NOT_PRESENT", "receipt": receipt, "path": str(path)}
    return {
        "status": "PASS",
        "receipt": receipt,
        "path": str(path),
        "content": json.loads(path.read_text()),
    }


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("BRAINK_MCP_TRANSPORT", "streamable-http"))
