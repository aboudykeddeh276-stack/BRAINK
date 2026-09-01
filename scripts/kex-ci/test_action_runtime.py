#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "modules" / "kex_wbos" / "action_server.py"
BASE = "http://127.0.0.1:8790"
REPORT = ROOT / "reports" / "kex-wbos" / "action-runtime-integration.json"


def request(path: str, payload: dict | None = None, method: str = "GET"):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def post_multipart(path: str, filename: str, raw: bytes):
    boundary = "----KEXActionBoundary"
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="workbook"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n",
        raw,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(BASE + path, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, response.read()


def require(value: bool, message: str):
    if not value:
        raise AssertionError(message)


def make_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "GENOME_STORE"
    ws.append(["flowId", "lineNo", "kexCode", "resonance"])
    ws.append(["FLOW-01", 1, "KEX-A", 0.297])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    proc = subprocess.Popen([sys.executable, str(SERVER)], cwd=ROOT)
    try:
        deadline = time.time() + 10
        while True:
            try:
                status, _, _ = request("/api/health")
                if status == 200:
                    break
            except Exception:
                pass
            if time.time() > deadline:
                raise AssertionError("action runtime did not become reachable")
            time.sleep(0.1)

        status, raw = post_multipart("/activate-workbook", "ACTION_TEST.xlsx", make_workbook())
        require(status == 200, "workbook activation failed")
        activation = json.loads(raw)
        require(activation.get("parse_state") == "STORED_AND_INDEXED", "workbook not indexed")

        _, _, raw = request("/workbooks/ACTION_TEST/tables/GENOME_STORE")
        table = json.loads(raw)
        require(table["rowCount"] == 1, "initial workbook table read failed")

        _, _, raw = request("/workbooks/ACTION_TEST/tables/GENOME_STORE/append", {
            "authority": "A.KEDDEH / KEDDEH_SYSTEMS / BRAINK / CASEPATH",
            "rows": [{"flowId": "FLOW-02", "lineNo": 2, "kexCode": "KEX-B", "resonance": 0.297}],
            "proofLedgerWrite": True,
        }, "POST")
        appended = json.loads(raw)
        require(appended["status"] == "MUTATED" and appended["mutated"] is True, "workbook append did not mutate")
        require(appended["beforeHash"] != appended["afterHash"], "workbook hash did not change")

        _, _, raw = request("/workbooks/ACTION_TEST/tables/GENOME_STORE")
        require(json.loads(raw)["rowCount"] == 2, "workbook append not visible in readback")

        _, _, raw = request("/notebooklm/sources/ingest", {
            "authority": "A.KEDDEH",
            "sourceText": "KEX action runtime source ingest proof",
            "sourceFormat": "text",
            "target": "KEX_RUNTIME_MODEL",
        }, "POST")
        ingest = json.loads(raw)
        require(ingest["status"] == "MUTATED" and ingest["afterHash"], "source ingest did not materialise")

        _, _, raw = request("/casepath/dispatch", {
            "packetId": "ACTION_TEST_PACKET",
            "activeTarget": "casepath.com.au",
            "actionQueue": [{"id": "TEST", "action": "trace"}],
            "proofTarget": "dispatch receipt",
        }, "POST")
        dispatch = json.loads(raw)
        require(dispatch["status"] == "MUTATED" and dispatch["mutated"], "casepath dispatch was not persisted")

        _, _, raw = request("/proof/ledger/write", {
            "authority": "A.KEDDEH",
            "eventType": "ACTION_RUNTIME_TEST",
            "payload": {"result": "executed"},
            "targetLedger": "KEX_ACTION_LEDGER",
        }, "POST")
        proof = json.loads(raw)
        require(proof["status"] == "MUTATED" and proof["afterHash"], "proof ledger did not mutate")

        _, _, raw = request("/deployment/dns/apply", {
            "authority": "A.KEDDEH",
            "providerRoute": "",
            "records": [{"name": "casepath.com.au", "type": "A", "value": "127.0.0.1"}],
        }, "POST")
        dns = json.loads(raw)
        require(dns["status"] == "BLOCKED" and dns["mutated"] is False, "DNS was falsely promoted without provider adapter")

        _, _, raw = request("/drive/writeback", {
            "authority": "A.KEDDEH",
            "targetPath": "/KEX/test.json",
            "content": {"test": True},
        }, "POST")
        drive = json.loads(raw)
        require(drive["status"] == "BLOCKED" and drive["mutated"] is False, "Drive writeback was falsely promoted without adapter")

        source_path = ingest["details"]["path"]
        _, _, raw = request("/runtime/readback", {
            "authority": "A.KEDDEH",
            "target": source_path,
            "expectedText": "source ingest proof",
        }, "POST")
        readback = json.loads(raw)
        require(readback["status"] == "VERIFIED" and readback["matched"], "local runtime readback failed")

        receipt = {
            "schema": "kex.action-runtime.integration.v1",
            "status": "PASS",
            "workbook_append": "MUTATED_AND_READ_BACK",
            "source_ingest": ingest["status"],
            "casepath_dispatch": dispatch["status"],
            "proof_write": proof["status"],
            "dns_without_adapter": dns["status"],
            "drive_without_adapter": drive["status"],
            "local_readback": readback["status"],
            "claimBoundary": "PASS proves local action-runtime mutation and blocker semantics only. It does not prove public DNS/TLS/router mutation, external Drive writeback, Bitcoin submission, or public deployment.",
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
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
