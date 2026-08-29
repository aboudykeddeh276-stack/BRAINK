from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from enterprise_portfolio_runtime import PortfolioRuntime, load_json


class EnterprisePortfolioRuntimeTests(unittest.TestCase):
    def test_sync_resolve_translate_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = PortfolioRuntime(root / "portfolio.sqlite3")
            try:
                sync = runtime.synchronise()
                self.assertGreaterEqual(sync["registry_count"], 4)
                self.assertGreaterEqual(sync["identity_count"], 14)
                self.assertGreaterEqual(sync["contract_count"], 7)
                self.assertIs(sync["global_stop"], False)

                identities = runtime.list_identities()
                self.assertTrue(any(row["canonical_id"] == "umbrella://keddeh/keo" for row in identities))

                resolved = runtime.resolve("umbrella://keddeh/keo")
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved["canonical_id"], "umbrella://keddeh/keo")

                registry = load_json("bilateral-contracts.json")
                contract = registry["contracts"][0]
                payload = {field: f"preserved:{field}" for field in contract["preserved_invariants"]}
                payload["document identity"] = "document://test/source"
                translated = runtime.translate(contract["id"], "document://test/source", payload)
                receipt = translated["receipt"]
                self.assertEqual(receipt["equivalence_state"], "SEMANTIC_EQUIVALENT_WITH_DECLARED_ADAPTERS")
                self.assertIs(receipt["global_stop"], False)
                self.assertEqual(set(translated["projection"]["preserved"]), set(contract["preserved_invariants"]))

                exported = runtime.export_snapshot(root / "export")
                snapshot = Path(exported["snapshot"])
                manifest = Path(exported["manifest"])
                self.assertTrue(snapshot.is_file())
                self.assertTrue(manifest.is_file())
                manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
                self.assertEqual(manifest_payload["files"][0]["sha256"], exported["sha256"])
            finally:
                runtime.close()

    def test_translation_rejects_missing_preserved_invariant(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = PortfolioRuntime(Path(temp) / "portfolio.sqlite3")
            try:
                runtime.synchronise()
                contract = load_json("bilateral-contracts.json")["contracts"][0]
                with self.assertRaisesRegex(ValueError, "missing_preserved_invariants"):
                    runtime.translate(contract["id"], "document://test/source", {})
            finally:
                runtime.close()

    def test_unknown_identity_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = PortfolioRuntime(Path(temp) / "portfolio.sqlite3")
            try:
                runtime.synchronise()
                self.assertIsNone(runtime.resolve("umbrella://keddeh/not-present"))
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
