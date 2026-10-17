from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from runtime.signal_fabric import SignalRequest
from runtime.runtime_registry import RuntimeRegistry
from modules.kex_wbos.workbook_api import dataset_response

BASE = Path(__file__).resolve().parents[1]
WEB_ROOT = BASE / "web" / "braink-copilot"
DEFAULT_TARGET = "app://braink/os"
REGISTRY_PATH = Path(os.getenv("KEX_RUNTIME_REGISTRY_PATH", "/var/lib/braink/signal-fabric/runtime_registry.sqlite"))
SIGNAL_BASE = os.getenv("KEX_SIGNAL_BASE", "http://127.0.0.1:18033").rstrip("/")


def _token() -> str:
    token = os.getenv("KEX_SIGNAL_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError("KEX_SIGNAL_AUTH_TOKEN must be configured")
    return token


def _authority() -> str:
    authority = os.getenv("KEX_SIGNAL_AUTHORITY", "")
    if not authority:
        raise RuntimeError("KEX_SIGNAL_AUTHORITY must be configured")
    return authority


def _signal_json(method: str, path: str, payload: dict[str, Any] | None = None, *, auth: bool = True) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if auth:
        headers["Authorization"] = f"Bearer {_token()}"
    req = urllib.request.Request(SIGNAL_BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"signal_service_http_{exc.code}:{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"signal_service_unreachable:{exc.reason}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("signal_service_invalid_json")
    return value


def _target_snapshot(target: str) -> dict[str, Any]:
    return _signal_json("GET", "/v1/state?target=" + urllib.parse.quote(target, safe=""))


def _operations() -> list[str]:
    health = _signal_json("GET", "/healthz", auth=False)
    return [str(item) for item in health.get("operations", [])]


def _compile_and_execute(target: str, operation: str, payload: dict[str, Any], *, source: str = "app://braink/copilot") -> dict[str, Any]:
    snapshot = _target_snapshot(target)
    request = SignalRequest.compile(
        source=source,
        target=target,
        operation=operation,
        state=snapshot.get("state", {}),
        payload=payload,
        invariants=("state_must_be_object", "no_null_state"),
        authority=_authority(),
        sequence=int(snapshot["next_sequence"]),
        previous_receipt=str(snapshot["head_receipt"]),
    )
    return _signal_json("POST", "/v1/propagate", asdict(request))


def boot_runtime() -> dict[str, Any]:
    receipt = _compile_and_execute(DEFAULT_TARGET, "STATE_PATCH", {"patch": {"runtime_status": "ONLINE", "runtime_mode": "COPILOT_FRONT_SURFACE"}})
    return {
        "status": "online",
        "target": DEFAULT_TARGET,
        "receipt": receipt,
        "claim_boundary": "This proves the BRAINK copilot control-plane target committed ONLINE state through the authenticated KEX signal service. It does not by itself prove a separate VM or external service started.",
    }


def ping_mesh() -> dict[str, Any]:
    runtimes = RuntimeRegistry(REGISTRY_PATH).list()
    nodes = [{
        "id": row["runtime_id"],
        "status": row.get("observed_state") or "UNKNOWN",
        "desired_state": row.get("desired_state"),
        "role": row.get("runtime_class") or "RUNTIME",
        "health_endpoint": row.get("health_endpoint"),
    } for row in runtimes]
    return {
        "status": "ok",
        "nodes": nodes,
        "registered": len(nodes),
        "signal_service": SIGNAL_BASE,
        "claim_boundary": "Mesh status is derived from the resident runtime registry. No unobserved remote node is reported as reachable.",
    }


def _skills() -> list[dict[str, Any]]:
    root = BASE / "skills"
    return [] if not root.exists() else [{"id": p.parent.name, "type": "skill", "path": p.relative_to(BASE).as_posix()} for p in sorted(root.rglob("SKILL.md"))]


def _modules() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for root in (BASE / "modules", BASE / "mcp"):
        if root.exists():
            for child in sorted(root.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    result.append({"id": child.name, "state": "RESIDENT", "path": child.relative_to(BASE).as_posix()})
    return result


def dashboard_summary() -> dict[str, Any]:
    rows = RuntimeRegistry(REGISTRY_PATH).list()
    nodes = [{"id": r["runtime_id"], "status": r.get("observed_state") or "UNKNOWN", "role": r.get("runtime_class") or "RUNTIME"} for r in rows]
    skills, modules = _skills(), _modules()
    active = sum(1 for r in rows if str(r.get("observed_state", "")).upper() in {"RUNNING", "ACTIVE", "ONLINE", "VERIFIED"})
    return {
        "nodes": nodes,
        "skills": skills,
        "modules": modules,
        "metrics": {"processActive": active, "processMax": max(len(rows), 1), "skillOpsPerMin": 0, "skillMaxOpsPerMin": max(len(skills), 1)},
        "signal": {"abi": "kex.signal/1", "operations": _operations(), "target": _target_snapshot(DEFAULT_TARGET)},
        "workbook": {
            "hyper_cores": dataset_response("hyper-cores"),
            "servers": dataset_response("servers"),
            "storage_devices": dataset_response("storage-devices"),
        },
        "claim_boundary": "Counts are derived from resident repository/runtime/workbook state. skillOpsPerMin remains zero because no measured operations-per-minute telemetry source is bound.",
    }


def chat_execute(task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    text, lower = task.strip(), task.strip().lower()
    if not text:
        raise ValueError("task_required")
    if any(term in lower for term in ("mesh status", "show mesh", "ping mesh", "nodes")):
        mesh = ping_mesh()
        return {"reply": f"Mesh registry: {mesh['registered']} runtime node(s) are resident. No remote reachability is inferred beyond observed registry state.", "route": "MESH_STATUS", "result": mesh}
    if any(term in lower for term in ("operation", "capabilit", "what can", "signal")):
        ops = _operations()
        return {"reply": "Bound machine operations: " + ", ".join(ops), "route": "OPERATION_MANIFEST", "result": {"operations": ops}}
    if "dashboard" in lower or "status" in lower:
        summary = dashboard_summary()
        return {"reply": f"Resident summary: {len(summary['nodes'])} runtimes, {len(summary['skills'])} skills, {len(summary['modules'])} modules.", "route": "DASHBOARD_SUMMARY", "result": summary}
    match = re.match(r"^\s*set\s+state\s+([A-Za-z0-9_.-]+)\s*=\s*(.+?)\s*$", text, re.IGNORECASE)
    if match:
        key, value = match.groups()
        receipt = _compile_and_execute(DEFAULT_TARGET, "STATE_PATCH", {"patch": {key: value}})
        return {"reply": f"Committed {key} to the BRAINK copilot target. Receipt {receipt['receipt_hash'][:16]}…", "route": "STATE_PATCH", "result": receipt}
    return {
        "reply": "No resident deterministic process route matched this task. A generative/chat model adapter is not currently bound to this service, so no fabricated AI response was produced.",
        "route": "UNBOUND_CHAT_SEMANTICS",
        "result": {"task": text, "context": context or {}, "available_routes": ["MESH_STATUS", "OPERATION_MANIFEST", "DASHBOARD_SUMMARY", "STATE_PATCH"]},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BRAINKCopilot/1.1"

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return self.headers.get("Authorization", "") == f"Bearer {_token()}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send_json(401, {"error": "unauthorized"})
        return False

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("json_object_required")
        return value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            path = WEB_ROOT / "index.html"
            if not path.exists():
                self._send_json(404, {"error": "front_surface_not_found"})
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/healthz":
            try:
                signal_health = _signal_json("GET", "/healthz", auth=False)
                self._send_json(200, {"status": "ok", "surface": "BRAINK_COPILOT", "signal": signal_health})
            except RuntimeError as exc:
                self._send_json(503, {"status": "degraded", "surface": "BRAINK_COPILOT", "detail": str(exc)})
            return
        if parsed.path == "/mesh/ping":
            if self._require_auth():
                self._send_json(200, ping_mesh())
            return
        if parsed.path == "/dashboards/summary":
            if not self._require_auth():
                return
            try:
                self._send_json(200, dashboard_summary())
            except RuntimeError as exc:
                self._send_json(503, {"error": "signal_service_dependency", "detail": str(exc)})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/braink/boot", "/chat/execute"}:
            self._send_json(404, {"error": "not_found"})
            return
        if not self._require_auth():
            return
        try:
            payload = self._read_json()
            result = boot_runtime() if self.path == "/braink/boot" else chat_execute(str(payload.get("task", "")), payload.get("context"))
            self._send_json(200, result)
        except (KeyError, ValueError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
            self._send_json(409, {"error": type(exc).__name__, "detail": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.getenv("BRAINK_COPILOT_QUIET") != "1":
            super().log_message(fmt, *args)


def main() -> None:
    _token(); _authority()
    host = os.getenv("BRAINK_COPILOT_HOST", "127.0.0.1")
    port = int(os.getenv("BRAINK_COPILOT_PORT", "8080"))
    WEB_ROOT.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
