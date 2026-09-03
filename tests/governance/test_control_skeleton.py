from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "governance" / "control_skeleton" / "generate_governance.py"
SPEC = ROOT / "governance" / "specs" / "public_tls_host_actuators.v1.json"

REQUIRED = {
    "CONTROL_INDEX.md",
    "FILING_STANDARD.md",
    "SCHEMA_STANDARD.md",
    "AUTHORSHIP_AUTHORITY.md",
    "PROCESS_CONTROL.md",
    "WORKFLOW_CONTROL.md",
    "OPERATIONS_RUNBOOK.md",
    "CROSS_PLATFORM_CONTRACT.md",
    "ACCOUNTABILITY_EVIDENCE.md",
    "KEY_CONSIDERATIONS.md",
    "GOVERNANCE_MANIFEST.json",
}


def test_generator_emits_complete_control_set(tmp_path: Path):
    out = tmp_path / "control"
    subprocess.run([sys.executable, str(GEN), "--spec", str(SPEC), "--output", str(out)], check=True)
    assert {p.name for p in out.iterdir()} == REQUIRED
    manifest = json.loads((out / "GOVERNANCE_MANIFEST.json").read_text())
    assert manifest["schema"] == "kex.braink.governance-manifest.v1"
    assert manifest["component_id"] == "BRAINK_PUBLIC_TLS_HOST_ACTUATORS"
    assert "PUBLIC_TLS_VERIFIED" in manifest["promotion_states"]
    targets = {x["target"] for x in manifest["dependencies"]}
    assert "repository://aboudykeddeh276-stack/SERVERS-KEDDEHSYSTEMS" in targets


def test_generator_refuses_implicit_overwrite(tmp_path: Path):
    out = tmp_path / "control"
    subprocess.run([sys.executable, str(GEN), "--spec", str(SPEC), "--output", str(out)], check=True)
    p = subprocess.run([sys.executable, str(GEN), "--spec", str(SPEC), "--output", str(out)], capture_output=True, text=True)
    assert p.returncode != 0
    assert "refusing to overwrite existing controls" in (p.stderr + p.stdout)


def test_spec_declares_cross_platform_and_accountability_fields():
    spec = json.loads(SPEC.read_text())
    assert spec["cross_platform"]["required_capabilities"]
    assert spec["evidence"]["receipt_schemas"]
    assert spec["proof_conditions"]
    assert spec["rollback_requirements"]
    assert spec["invalid_claims"]
