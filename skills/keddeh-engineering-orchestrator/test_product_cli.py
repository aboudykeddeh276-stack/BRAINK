import json
import tempfile
import unittest
from pathlib import Path

import keo


class KeoProductCliTests(unittest.TestCase):
    def test_all_profiles_initialise_validate_and_inspect(self) -> None:
        for profile in keo.SUPPORTED_PROFILES:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / profile
                args = type(
                    "Args",
                    (),
                    {
                        "directory": str(target),
                        "name": f"Test {profile}",
                        "slug": f"test-{profile}",
                        "profile": profile,
                        "force": False,
                    },
                )()
                self.assertEqual(keo.command_init(args), 0)
                self.assertEqual(keo.validate_project(target), [])
                self.assertEqual(set(path.name for path in target.iterdir()), set(keo.REQUIRED_FILES))

    def test_identity_is_preserved_across_project_kir_and_topology(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "server"
            args = type(
                "Args",
                (),
                {
                    "directory": str(target),
                    "name": "Identity Server",
                    "slug": "identity-server",
                    "profile": "server",
                    "force": False,
                },
            )()
            keo.command_init(args)
            project = json.loads((target / "keo.project.json").read_text(encoding="utf-8"))
            kir = json.loads((target / "kir.json").read_text(encoding="utf-8"))
            topology = json.loads((target / "topology.json").read_text(encoding="utf-8"))
            self.assertEqual(project["system_id"], kir["system_id"])
            self.assertEqual(project["system_id"], topology["system_id"])

    def test_validator_reports_exact_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            errors = keo.validate_project(target)
            self.assertIn("missing:keo.project.json", errors)
            self.assertIn("missing:kir.json", errors)

    def test_duplicate_topology_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "hal"
            args = type(
                "Args",
                (),
                {
                    "directory": str(target),
                    "name": "HAL",
                    "slug": "hal",
                    "profile": "hardware-abstraction",
                    "force": False,
                },
            )()
            keo.command_init(args)
            topology_path = target / "topology.json"
            topology = json.loads(topology_path.read_text(encoding="utf-8"))
            topology["nodes"].append(dict(topology["nodes"][0]))
            topology_path.write_text(json.dumps(topology), encoding="utf-8")
            self.assertIn("topology:duplicate_node_identity", keo.validate_project(target))

    def test_product_is_local_only_and_dependency_free(self) -> None:
        manifest = json.loads((Path(__file__).resolve().parent / "product_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["privacy_default"], "LOCAL_ONLY_NO_SOURCE_UPLOAD")
        self.assertEqual(manifest["cli"]["third_party_runtime_dependencies"], [])
        self.assertNotIn("Lovable", manifest["primary_interfaces"])
        self.assertIn("Lovable", manifest["excluded_tools"])


if __name__ == "__main__":
    unittest.main()
