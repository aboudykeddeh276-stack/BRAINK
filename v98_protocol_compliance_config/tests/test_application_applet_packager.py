from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_application_applet_packager as packager


class ApplicationAppletPackagerTests(unittest.TestCase):
    def test_all_service_modules_are_assessed(self) -> None:
        result = packager.run_application_applet_shipping(ROOT, emit_receipt=True)
        service_count = len(packager.load_services(ROOT))
        # Plus at least the root KEX workstation application.
        self.assertGreaterEqual(result["receipt"]["assessed_components"], service_count + 1)
        self.assertTrue(result["all_modules_assessed_as_packages"])

    def test_every_assessed_component_has_k_app_files_and_manifest_readback(self) -> None:
        result = packager.run_application_applet_shipping(ROOT, emit_receipt=True)
        for row in result["assessments"]:
            self.assertEqual(row["shipping_state"], "LOCAL_SHIPPABLE_K_APP", row)
            self.assertTrue(row["integrity_readback_before_node_execution"], row)
            self.assertTrue(row["runtime_contract_complete"], row)
            self.assertTrue(row["k_app_files_complete"], row)
            manifest_path = Path(row["manifest_path"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["canonicalRuntimeRule"], "DEPENDENCY_FAILURE_NE_GLOBAL_APPLICATION_FAILURE")
            self.assertIn("dependency-contracts.json", {p.name for p in manifest_path.parent.iterdir()})
            self.assertIn("degraded-mode-policy.json", {p.name for p in manifest_path.parent.iterdir()})

    def test_required_runtime_independence_contract_fields_are_present(self) -> None:
        app_packager = packager.ApplicationAppletPackager(ROOT)
        for spec in app_packager.component_specs():
            manifest = app_packager.manifest_for(spec)
            contract = manifest["runtimeIndependenceContract"]
            for field in app_packager.registry["required_runtime_contract_fields"]:
                self.assertIn(field, contract)
                self.assertNotIn(contract[field], (None, "", []))

    def test_receipt_matrix_catalog_and_outbox_are_written(self) -> None:
        result = packager.run_application_applet_shipping(ROOT, emit_receipt=True)
        receipt = result["receipt"]
        self.assertEqual(receipt["integrity_failures"], 0)
        self.assertEqual(receipt["missing_contracts"], 0)
        self.assertTrue(Path(receipt["receipt_path"]).exists())
        self.assertTrue(Path(receipt["catalog_path"]).exists())
        self.assertTrue(Path(receipt["outbox_manifest"]).exists())
        self.assertTrue((ROOT / "exports" / "application_applet_shipping_matrix.csv").exists())

    def test_shipping_does_not_use_simulation_or_telemetry_as_proof(self) -> None:
        result = packager.run_application_applet_shipping(ROOT, emit_receipt=True)
        self.assertFalse(result["simulation_used_as_shipping_proof"])
        self.assertFalse(result["telemetry_used_as_shipping_proof"])
        self.assertFalse(result["global_failure_from_dependency_failure"])


if __name__ == "__main__":
    unittest.main()
