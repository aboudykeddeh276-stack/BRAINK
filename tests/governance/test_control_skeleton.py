from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "governance" / "control_skeleton" / "generate_governance.py"
REGISTRY_DRIVER = ROOT / "governance" / "control_skeleton" / "scaffold_registry.py"
REGISTRY = ROOT / "governance" / "GOVERNANCE_TARGET_REGISTRY.json"
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


def test_registry_tracks_unspecified_targets_without_inventing_specs():
    registry = json.loads(REGISTRY.read_text())
    assert registry["schema"] == "kex.braink.governance-target-registry.v1"
    targets = {t["component_id"]: t for t in registry["targets"]}
    assert targets["PUBLIC_TLS_HOST_ACTUATORS"]["state"] == "SPECIFIED"
    assert targets["PUBLIC_TLS_HOST_ACTUATORS"]["spec"].endswith("public_tls_host_actuators.v1.json")
    assert targets["IL_LLM"]["state"] == "DISCOVERY_REQUIRED"
    assert "spec" not in targets["IL_LLM"]
    assert targets["VFS_K_DRIVE"]["state"] == "DISCOVERY_REQUIRED"


def test_registry_preserves_external_mirror_lane_ownership_and_consumer_contract():
    registry = json.loads(REGISTRY.read_text())
    targets = {t["component_id"]: t for t in registry["targets"]}
    mirror = targets["KEX_MIRROR_LANE_STATE_TRANSFER_R1"]
    assert mirror["state"] == "SPECIFIED"
    assert mirror["classification"] == "RUNTIME_STATE_TRANSFER_ACTUATOR"
    assert mirror["repository"] == "aboudykeddeh276-stack/KEDDEH-CLOUD-SERVERS-ID-1"
    assert mirror["sector"] == "CLOUD_INFRASTRUCTURE_MIRROR_LANE"
    assert mirror["external_spec"] == "mirror_lane_storage_substrate/MIRROR_LANE_COMPONENT_SPEC.json"
    assert mirror["external_control_index"] == "mirror_lane_storage_substrate/CONTROL_INDEX.md"
    assert mirror["consumer"] == "enterprise/mirror_lane_transfer_adapter.py"
    assert mirror["qualification_claim"] == "BRAINK_LOGICAL_COMPUTER_HOST_INDEPENDENCE_R1"
    # Sector-level cloud governance remains separately unresolved; specifying one child
    # runtime must not silently promote the whole cloud sector.
    assert targets["CLOUD_INFRASTRUCTURE"]["state"] == "DISCOVERY_REQUIRED"


def test_registry_driver_generates_only_specified_component(tmp_path: Path):
    out = tmp_path / "generated"
    p = subprocess.run(
        [
            sys.executable,
            str(REGISTRY_DRIVER),
            "--registry",
            str(REGISTRY),
            "--output-root",
            str(out),
            "--component-id",
            "PUBLIC_TLS_HOST_ACTUATORS",
        ],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr + p.stdout
    generated = out / "PUBLIC_TLS_HOST_ACTUATORS"
    assert generated.is_dir()
    assert {p.name for p in generated.iterdir()} == REQUIRED
    result = json.loads(p.stdout)
    assert result["results"][0]["status"] == "GENERATED"
