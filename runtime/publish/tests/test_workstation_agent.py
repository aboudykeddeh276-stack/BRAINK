from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import urllib.request
from pathlib import Path


def _load_agent():
    script = Path(__file__).resolve().parents[1] / "scripts" / "workstation_agent.py"
    spec = importlib.util.spec_from_file_location("braink_workstation_agent", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workstation_service_boot_health_and_content(tmp_path, monkeypatch):
    agent = _load_agent()
    html = tmp_path / "workstation.html"
    payload = b"<!doctype html><title>BRAINK</title><script>window.BRAINK_TEST=1;</script>"
    html.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    monkeypatch.setenv("BRAINK_WORKSTATION_HTML", str(html))
    monkeypatch.setenv("BRAINK_WORKSTATION_SHA256", digest)
    monkeypatch.setenv("BRAINK_WORKSTATION_BIND", "127.0.0.1")
    monkeypatch.setenv("BRAINK_WORKSTATION_PORT", "0")
    monkeypatch.setattr(agent, "DATA", tmp_path / "data")

    transition = agent.build_transition()
    assert transition["receipt"]["status"] == "PASS"
    assert transition["validation"] == "PASS"
    assert transition["next_state"] == "WORKSTATION_BOOT:QUALIFIED"

    observed = transition["receipt"]["observed"]
    with urllib.request.urlopen(observed["health"], timeout=2) as response:
        health = json.loads(response.read().decode("utf-8"))
    assert health["status"] == "PASS"
    assert health["sha256"] == digest

    with urllib.request.urlopen(observed["url"], timeout=2) as response:
        served = response.read()
        served_digest = response.headers["X-BRAINK-Workstation-SHA256"]
    assert served == payload
    assert served_digest == digest

    receipt = json.loads((agent.DATA / "workstation_service_receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "WORKSTATION_SERVICE_RUNNING"
    assert receipt["sha256"] == digest
    agent.shutdown_servers()


def test_workstation_probe_blocks_when_unbound(monkeypatch):
    agent = _load_agent()
    monkeypatch.delenv("BRAINK_WORKSTATION_HTML", raising=False)
    try:
        agent.resolve_workstation()
    except RuntimeError as exc:
        assert str(exc) == "BLOCKED:BRAINK_WORKSTATION_HTML_UNBOUND"
    else:
        raise AssertionError("Expected unbound workstation to block")


def test_workstation_rejects_hash_mismatch(tmp_path, monkeypatch):
    agent = _load_agent()
    html = tmp_path / "workstation.html"
    html.write_text("<html>one</html>", encoding="utf-8")
    monkeypatch.setenv("BRAINK_WORKSTATION_HTML", str(html))
    monkeypatch.setenv("BRAINK_WORKSTATION_SHA256", "0" * 64)
    try:
        agent.resolve_workstation()
    except RuntimeError as exc:
        assert str(exc).startswith("FAILED:WORKSTATION_SHA256_MISMATCH:")
    else:
        raise AssertionError("Expected hash mismatch failure")
