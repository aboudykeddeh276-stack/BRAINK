from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from deployment.kex_runtime_service_r40 import build_server


TOKEN = "r40-test-token-0123456789abcdef0123456789"


def _request(server, path, body=None, token=None):
    host, port = server.server_address[:2]
    url = f"http://127.0.0.1:{port}{path}"
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None: headers["Authorization"] = "Bearer " + token
    req = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _correction():
    return {
        "source": "test://http/correction",
        "data_class": "CORRECTION",
        "payload": {"via": "http"},
        "authority": "authority://source/local",
        "capabilities": ["process", "readback"],
        "illlm": {"intent": "state.write", "lineage": "A", "key": "http_r40", "value": 1},
    }


def test_http_projection_requires_authentication(tmp_path):
    server = build_server(tmp_path / "state", port=0, auth_token=TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        status, body = _request(server, "/v1/canonical/execute", _correction())
        assert status == 401
        assert body["status"] == "UNAUTHORIZED"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_authenticated_http_executes_same_canonical_graph(tmp_path):
    server = build_server(tmp_path / "state", port=0, auth_token=TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        status, body = _request(server, "/v1/canonical/execute", _correction(), TOKEN)
        assert status == 200
        assert body["readback"]["state"]["http_r40"] == 1
        assert body["readback"]["ledger_verified"] is True
        assert "IL_LLM_RESOLVED" in body["stages"] and "READBACK" in body["stages"]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_http_preserves_canonical_blocked_state(tmp_path):
    server = build_server(tmp_path / "state", port=0, auth_token=TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        cmd = _correction(); cmd["capabilities"] = ["not_a_capability"]
        status, body = _request(server, "/v1/canonical/execute", cmd, TOKEN)
        assert status == 409
        assert body["status"] == "BLOCKED:UNKNOWN_CAPABILITY:not_a_capability"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_canonical_status_readback_is_authenticated(tmp_path):
    server = build_server(tmp_path / "state", port=0, auth_token=TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        status, _ = _request(server, "/v1/canonical/status")
        assert status == 401
        status, body = _request(server, "/v1/canonical/status", token=TOKEN)
        assert status == 200
        assert body["runtime"]["status"] == "READY"
        assert body["fabric"]["ledger_verified"] is True
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
