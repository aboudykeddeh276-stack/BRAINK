from pathlib import Path

from enterprise.self_addressing_runtime import SelfAddressingRuntime


def test_successful_read_observation_drops_full_value_but_keeps_proof(tmp_path: Path):
    runtime = SelfAddressingRuntime(tmp_path / "checkpoint.json")
    backing = f"file://{tmp_path / 'large.json'}"
    value = {"items": list(range(2048))}

    write = runtime.route("computer://A/test", backing, "WRITE", value)
    assert write["status"] == "COMMITTED"
    read = runtime.route("computer://A/test", backing, "READ")
    assert read["value"] == value

    observed = runtime.observers[-1]["payload"]
    assert observed["status"] == "READ"
    assert "value" not in observed
    assert observed["value_root"] == read["value_hash"]
    assert observed["value_bytes"] > 0


def test_failure_payload_is_preserved_in_full(tmp_path: Path):
    runtime = SelfAddressingRuntime(tmp_path / "checkpoint.json")
    payload = {"status": "CONFLICT", "expected_hash": "a", "current_hash": "b", "detail": {"why": "stale"}}
    event = runtime.observe("runtime://test", "computer://A/state", "CONTRADICTION", payload)
    assert event["payload"] == payload
