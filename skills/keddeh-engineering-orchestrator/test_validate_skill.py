import json
import unittest

from validate_skill import ROOT, validate


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class EngineeringOrchestratorSkillTests(unittest.TestCase):
    def test_skill_contract_is_valid(self) -> None:
        self.assertEqual(validate(), [])

    def test_topology_levels_are_ordered_and_complete(self) -> None:
        manifest = load("skill_manifest.json")
        self.assertEqual(
            manifest["topology_levels"],
            [
                "L0_ECOSYSTEM",
                "L1_SYSTEM",
                "L2_DOMAIN",
                "L3_RUNTIME_CONTAINER",
                "L4_COMPONENT",
                "L5_CODE_UNIT",
                "L6_EXECUTION_TRANSITION",
                "L7_DEPLOYMENT_PROJECTION",
            ],
        )

    def test_iteration_lifecycle_cannot_skip_design_and_validation(self) -> None:
        lifecycle = load("iteration_lifecycle.json")
        states = [state["id"] for state in lifecycle["iteration_states"]]
        self.assertLess(states.index("I2_DESIGN"), states.index("I3_IMPLEMENT"))
        self.assertLess(states.index("I4_STATIC_VALIDATE"), states.index("I7_PROMOTE"))
        self.assertLess(states.index("I8_PRESERVE"), states.index("I9_REVIEW"))

    def test_naming_conventions_include_topology_and_iteration_identities(self) -> None:
        naming = load("naming_conventions.json")
        kinds = set(naming["allowed_identity_kinds"])
        self.assertTrue({"system", "domain", "service", "component", "topology", "iteration"}.issubset(kinds))
        self.assertEqual(naming["segment_case"], "lower-kebab-case")

    def test_topology_schema_forbids_global_stop(self) -> None:
        schema = load("software_topology.schema.json")
        self.assertIs(schema["properties"]["global_stop"]["const"], False)

    def test_all_canonical_files_exist(self) -> None:
        manifest = load("skill_manifest.json")
        for filename in manifest["canonical_files"].values():
            self.assertTrue((ROOT / filename).exists(), filename)


if __name__ == "__main__":
    unittest.main()
