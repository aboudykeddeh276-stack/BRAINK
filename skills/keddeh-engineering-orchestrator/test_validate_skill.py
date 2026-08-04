import json
from pathlib import Path

from validate_skill import ROOT, validate


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_skill_contract_is_valid() -> None:
    assert validate() == []


def test_topology_levels_are_ordered_and_complete() -> None:
    manifest = load("skill_manifest.json")
    assert manifest["topology_levels"] == [
        "L0_ECOSYSTEM",
        "L1_SYSTEM",
        "L2_DOMAIN",
        "L3_RUNTIME_CONTAINER",
        "L4_COMPONENT",
        "L5_CODE_UNIT",
        "L6_EXECUTION_TRANSITION",
        "L7_DEPLOYMENT_PROJECTION",
    ]


def test_iteration_lifecycle_cannot_skip_design_and_validation() -> None:
    lifecycle = load("iteration_lifecycle.json")
    states = [state["id"] for state in lifecycle["iteration_states"]]
    assert states.index("I2_DESIGN") < states.index("I3_IMPLEMENT")
    assert states.index("I4_STATIC_VALIDATE") < states.index("I7_PROMOTE")
    assert states.index("I8_PRESERVE") < states.index("I9_REVIEW")


def test_naming_conventions_include_topology_and_iteration_identities() -> None:
    naming = load("naming_conventions.json")
    kinds = set(naming["allowed_identity_kinds"])
    assert {"system", "domain", "service", "component", "topology", "iteration"}.issubset(kinds)
    assert naming["segment_case"] == "lower-kebab-case"


def test_topology_schema_forbids_global_stop() -> None:
    schema = load("software_topology.schema.json")
    assert schema["properties"]["global_stop"]["const"] is False


def test_all_canonical_files_exist() -> None:
    manifest = load("skill_manifest.json")
    for filename in manifest["canonical_files"].values():
        assert (ROOT / filename).exists(), filename
