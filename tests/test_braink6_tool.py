import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from braink6_tool import BrainK6, Capability, TaskEnvelope


def test_task_identity_persists_through_capability_execution(tmp_path):
    b = BrainK6(tmp_path / ".braink6")
    task = b.put_task(TaskEnvelope("T-1", "Build tool", "Execute through BRAINK^6", ["receipt"] , obligations=["run validator"]))
    b.put_capability(Capability("CAP-1", "validated command execution", ["python"], [[sys.executable, "-c", "assert 2+7 == 9"]]))
    unlock = b.unlock("CAP-1")
    assert unlock["payload"]["capability"]["state"] == "UNLOCKED"
    receipt = b.execute("CAP-1", [sys.executable, "-c", "print('executed')"])
    assert receipt["payload"]["task_id"] == "T-1"
    assert receipt["payload"]["task_hash"] == task["task_hash"]
    assert receipt["payload"]["result"]["returncode"] == 0


def test_failed_validator_cannot_unlock(tmp_path):
    b = BrainK6(tmp_path / ".braink6")
    b.put_task(TaskEnvelope("T-2", "Reject claim", "Do not claim failed skills", ["locked"] ))
    b.put_capability(Capability("BAD", "must fail", [], [[sys.executable, "-c", "raise SystemExit(7)"]]))
    receipt = b.unlock("BAD")
    assert receipt["payload"]["capability"]["state"] == "VALIDATION_FAIL"
    try:
        b.execute("BAD", [sys.executable, "-c", "print('must not run')"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("locked capability executed")


def test_seed_corruption_is_detected(tmp_path):
    b = BrainK6(tmp_path / ".braink6")
    b.put_task(TaskEnvelope("T-3", "Integrity", "Reject corrupted skill", ["corruption detected"] ))
    b.put_capability(Capability("CAP-X", "original", [], [[sys.executable, "-c", "pass"]]))
    path = tmp_path / ".braink6" / "capabilities" / "CAP-X.json"
    data = json.loads(path.read_text())
    data["purpose"] = "corrupted after sealing"
    path.write_text(json.dumps(data))
    receipt = b.unlock("CAP-X")
    assert receipt["payload"]["capability"]["state"] == "CORRUPTED"
