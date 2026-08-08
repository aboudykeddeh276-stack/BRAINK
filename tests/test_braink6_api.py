import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from braink6_api import BrainK6Runtime


def test_python_skill_reconstructs_before_execution(tmp_path):
    r = BrainK6Runtime(tmp_path / ".braink6")
    r.task("APEX-1", "BRAINK6 apex", "Execute only reconstructed Python", acceptance=["receipt"])
    cap = r.define_python()
    assert cap["state"] == "SEEDED"
    receipt = r.unlock("PYTHON")
    assert receipt["payload"]["capability"]["state"] == "UNLOCKED"
    out = r.run_python("print(2 + 7)")
    assert out["payload"]["result"]["stdout"].strip() == "9"
    assert out["payload"]["task_id"] == "APEX-1"


def test_workspace_is_real_directory_and_inspectable(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    r = BrainK6Runtime(tmp_path / ".state")
    info = r.inspect_workspace(tmp_path)
    assert info["python_file_count"] >= 1
    assert "a.py" in info["python_files"]


def test_task_identity_survives_workspace_operation(tmp_path):
    r = BrainK6Runtime(tmp_path / ".braink6")
    r.task("PARENT", "Parent", "Do not drop task", obligations=["inspect", "continue"])
    (tmp_path / "code.py").write_text("print('ok')\n")
    r.inspect_workspace(tmp_path)
    assert r.status()["task"]["task_id"] == "PARENT"
    assert r.status()["task"]["obligations"] == ["inspect", "continue"]
