from __future__ import annotations

import copy

import runtime.btc_vertical_closure as vertical


TEMPLATE = {
    "height": 900000,
    "previousblockhash": "11" * 32,
    "version": 0x20000000,
    "bits": "1d00ffff",
    "curtime": 1750000000,
    "coinbasevalue": 312500000,
    "transactions": [],
    "workid": "fixture-work-vertical",
}


def test_core_unobserved_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(vertical, "VERTICAL_RECEIPT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(vertical, "VERTICAL_LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(vertical, "start_or_resolve_node", lambda: {"attempted": False})
    monkeypatch.setattr(vertical, "check_rpc", lambda: (False, {"error": "offline"}))
    result = vertical.execute_vertical_closure()
    assert result["stage"] == "CORE_AUTHORITY"
    assert result["status"] == "UNOBSERVED"


def test_vertical_path_uses_existing_solver_and_submission_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(vertical, "VERTICAL_RECEIPT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(vertical, "VERTICAL_LEDGER_PATH", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(vertical, "LIVE_TEMPLATE_PATH", tmp_path / "template.json")
    monkeypatch.setattr(vertical, "LIVE_CANDIDATE_PATH", tmp_path / "candidate.json")
    monkeypatch.setattr(vertical, "start_or_resolve_node", lambda: {"attempted": False, "reason": "rpc_already_available"})
    monkeypatch.setattr(vertical, "check_rpc", lambda: (True, {"chain": "main", "bestblockhash": TEMPLATE["previousblockhash"], "initialblockdownload": False}))
    monkeypatch.setattr(vertical, "request_template", lambda: (True, copy.deepcopy(TEMPLATE)))
    monkeypatch.setattr(vertical, "rpc_call", lambda method, params=None: TEMPLATE["previousblockhash"] if method == "getbestblockhash" else None)
    monkeypatch.setattr(vertical, "run_command", lambda variable, template_path, result_path=None: {"attempted": True, "candidate": None})
    result = vertical.execute_vertical_closure()
    assert result["run_id"]
    assert result["stage"] == "CANDIDATE"
    assert result["status"] == "UNOBSERVED"
    assert any(record["stage"] == "CORE_AUTHORITY" for record in result["evidence"])
