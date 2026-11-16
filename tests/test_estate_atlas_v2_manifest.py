#!/usr/bin/env python3
"""Tests the committed source/count manifest for the estate atlas v2."""
import json
import re
import unittest
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "docs" / "estate" / "ATLAS_V2_SOURCE_MANIFEST.json"

class AtlasManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_authority_and_schema(self):
        self.assertEqual(self.data["schema"], "KS-BRAINK-IL-LLM/estate-atlas-v2-source-manifest/1")
        self.assertEqual(self.data["architect"], "A. Keddeh")
        self.assertEqual(self.data["canonicalArchitecture"], "KS-BRAINK-IL-LLM")

    def test_registry_counts(self):
        c = self.data["counts"]
        self.assertEqual((c["r5Identities"], c["p11LogicalObjects"], c["r5P11Overlap"]), (33, 76, 23))
        self.assertEqual((c["r5OnlyLogicalIdentities"], c["unionLogicalIdentities"]), (10, 86))
        self.assertEqual((c["uniqueCarriers"], c["rawCarrierRows"], c["duplicateCarrierRows"]), (95, 98, 3))
        self.assertEqual((c["multiCarrierLogicalObjects"], c["carrierBytesRepresented"]), (19, 6630073))
        self.assertEqual(c["priorEnrichedEntriesPreserved"], 12)

    def test_r5_only_identity_set(self):
        ids = self.data["r5OnlyIdentities"]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("braink://volume/r5/system-orchestrator", ids)
        self.assertIn("app://casepath/analytical-matter-mesh/v18", ids)

    def test_integrity_algorithm_not_invented(self):
        self.assertEqual(self.data["integrityField"]["sourceColumn"], "Integrity")
        self.assertEqual(self.data["integrityField"]["algorithm"], "UNSPECIFIED")

    def test_artifact_hashes_and_verification(self):
        for artifact in self.data["generatedArtifacts"]:
            self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(artifact["bytes"], 0)
        v = self.data["verification"]
        self.assertEqual((v["atlasTests"], v["atlasPassed"], v["atlasFailed"], v["atlasExitCode"]), (8, 8, 0, 0))
        self.assertEqual((v["manifestTests"], v["manifestPassed"], v["manifestFailed"], v["manifestExitCode"]), (6, 6, 0, 0))
        self.assertEqual(v["javascriptExitCode"], 0)

    def test_boundaries_are_explicit(self):
        claims = " ".join(self.data["claimBoundaries"]).lower()
        self.assertIn("not materialize", claims)
        self.assertIn("subjective consciousness", claims)

if __name__ == "__main__":
    unittest.main(verbosity=2)
