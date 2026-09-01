#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "modules" / "kex_wbos" / "server.py"
OPENAPI = ROOT / "openapi" / "kex-unified-api.yaml"
LEDGER = ROOT / "reports" / "kex-wbos" / "proof-ledger.jsonl"
BASE = "http://127.0.0.1:8765"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=5) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def post_multipart(path: str, fields: dict[str, tuple[str, bytes]]):
    boundary = "----KEXBoundary7MA4YWxkTrZu0gW"
    chunks: list[bytes] = []
    for name, (filename, payload) in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n",
            payload,
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def workbook_bytes(sheet_name: str, value: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws["A1"] = value
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if LEDGER.exists():
        LEDGER.unlink()

    spec = OPENAPI.read_text(encoding="utf-8")
    required_paths = [
        "/core-lattice:", "/flow-territories:", "/genome-store:", "/kex-dna:",
        "/substrate-grid:", "/system-state:", "/root-matrix:",
        "/activate-workbook:", "/workbooks/apply:", "/virtualization-metrics:",
        "/api/health:", "/api/resolve:", "/mesh:", "/cascade:", "/api/proof-ledger:",
    ]
    require("openapi: 3.1.0" in spec, "OpenAPI version missing")
    for required in required_paths:
        require(required in spec, f"Unified OpenAPI surface missing: {required}")

    proc = subprocess.Popen([sys.executable, str(SERVER)], cwd=ROOT)
    try:
        deadline = time.time() + 10
        while True:
            try:
                status, _, _ = get("/api/health")
                if status == 200:
                    break
            except Exception:
                pass
            if time.time() >= deadline:
                raise AssertionError("WBOS server did not become reachable")
            time.sleep(0.1)

        status, ctype, apex = get("/")
        require(status == 200 and "text/html" in ctype and b"KEX K.0 Apex" in apex, "apex projection failed")

        _, _, raw = get("/api/health")
        health = json.loads(raw)
        require(health["status"] == "ok", "health not ok")
        require(health["os"] == "KEX-WBOS Cascade OS", "wrong OS identity")
        require(len(health["cascade_order"]) == 10, "cascade order incomplete")

        for endpoint in [
            "/core-lattice", "/flow-territories", "/genome-store", "/kex-dna",
            "/substrate-grid", "/system-state", "/work-log", "/global-index",
            "/root-matrix", "/benchmarks", "/hyper-cores", "/servers",
            "/storage-devices", "/logs",
        ]:
            _, _, raw = get(endpoint)
            payload = json.loads(raw)
            require(payload["state"] == "SOURCE_NOT_RESIDENT", f"{endpoint} over-promoted source state")
            require(payload["rows"] == [], f"{endpoint} invented workbook rows")

        _, _, raw = get("/root-matrix/statistics")
        stats = json.loads(raw)
        require(stats["state"] == "SOURCE_NOT_RESIDENT" and stats["count"] == 0, "root matrix statistics boundary failed")

        _, _, raw = get("/virtualization-metrics")
        metrics = json.loads(raw)
        require(metrics["state"] == "UNMEASURED", "virtualization metrics were fabricated")

        uri = urllib.parse.quote("KEX://ROOT/WORKBOOK/CORE_LATTICE", safe="")
        _, _, raw = get(f"/api/resolve?uri={uri}")
        resolved = json.loads(raw)
        require(resolved["result"]["found"] is True, "workbook KEX URI did not resolve")

        first = workbook_bytes("CORE_LATTICE", "KEX-A")
        second = workbook_bytes("KEX_DNA", "KEX-B")

        status, _, raw = post_multipart("/activate-workbook", {"workbook": ("seed-a.xlsx", first)})
        activation = json.loads(raw)
        require(status == 200, "workbook activation request failed")
        require(activation["signal"] == "WORKBOOK_STORED_FOR_RESOLUTION", "workbook activation receipt invalid")
        require(activation["bytes"] == len(first), "activation byte count mismatch")

        status, ctype, combined = post_multipart(
            "/workbooks/apply",
            {"workbook1": ("a.xlsx", first), "workbook2": ("b.xlsx", second)},
        )
        require(status == 200, "workbook apply failed")
        require("spreadsheetml.sheet" in ctype, "combined workbook content type wrong")
        wb = load_workbook(io.BytesIO(combined), data_only=False)
        require("A_CORE_LATTICE" in wb.sheetnames, "first workbook sheet not materialised")
        require("B_KEX_DNA" in wb.sheetnames, "second workbook sheet not materialised")
        require(wb["A_CORE_LATTICE"]["A1"].value == "KEX-A", "first workbook value not preserved")
        require(wb["B_KEX_DNA"]["A1"].value == "KEX-B", "second workbook value not preserved")

        _, _, raw = get("/mesh")
        mesh = json.loads(raw)
        require(mesh["state"] == "LOCAL_REGISTRY_ONLY", "mesh boundary was over-promoted")

        _, _, raw = get("/cascade")
        cascade = json.loads(raw)
        require(cascade["root"] == "KEX://ROOT/OS", "cascade root mismatch")

        _, _, raw = get("/api/proof-ledger")
        entries = json.loads(raw)["entries"]
        events = {e["event"] for e in entries}
        for event in [
            "WBOS_BOOT", "HEALTH_READ", "PROJECT_UI", "RESOLVE_KEX_URI",
            "WORKBOOK_DATA_READ", "ROOT_MATRIX_STATISTICS", "ACTIVATE_WORKBOOK",
            "APPLY_WORKBOOKS", "MESH_STATUS_READ", "CASCADE_READ",
        ]:
            require(event in events, f"proof event missing: {event}")

        receipt = {
            "schema": "kex.unified.integration-test.v2",
            "state": "PASS",
            "server_process": "executed",
            "workbook_data_routes_checked": 14,
            "workbook_source_boundary": "SOURCE_NOT_RESIDENT",
            "workbook_activation": "executed",
            "workbook_apply": "executed_and_read_back",
            "proof_entries": len(entries),
            "mesh_boundary": mesh["state"],
            "claim_boundary": "This proves local Unified API execution, workbook byte activation, XLSX combination/readback, route resolution and proof mutation in the GitHub job/runtime context. It does not prove the historical 29-workbook/662-sheet corpus is resident, public deployment, external mesh connectivity, browser IndexedDB execution, or physical storage provisioning."
        }
        out = ROOT / "reports" / "kex-wbos" / "integration.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
