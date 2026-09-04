import hashlib
import json
import subprocess
import sys

from research.qualification_fabric.executor_probe import probe


def test_executor_probe_is_available_in_current_executor():
    result = probe()
    assert result["schema"] == "braink.kex.qualification-executor.v1"
    assert result["availability"] == "AVAILABLE"
    assert len(result["environment_fingerprint"]) == 64
    assert "process_spawn" in result["capabilities"]
    assert "tcp_loopback" in result["capabilities"]
    assert "sqlite" in result["capabilities"]
    assert "filesystem_mutation" in result["capabilities"]


def test_executor_probe_fingerprint_is_derived_from_observed_environment():
    result = probe()
    assert result["environment_fingerprint"] == hashlib.sha256(
        json.dumps(
            {"platform": __import__("platform").platform(), "machine": __import__("platform").machine(), "checks": result["probe"]},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def test_probe_cli_emits_machine_readable_receipt():
    completed = subprocess.run(
        [sys.executable, "-m", "research.qualification_fabric.executor_probe"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    receipt = json.loads(completed.stdout)
    assert receipt["availability"] == "AVAILABLE"
    assert receipt["executor_id"] == "runtime-probe"
