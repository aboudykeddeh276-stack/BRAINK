#!/usr/bin/env python3
"""Regression checks for the R4 source verification summary."""
import json
import re
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "docs" / "estate" / "ROOT_R4_VFS_VERIFICATION.json"

class R4VerificationSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PATH.read_text(encoding="utf-8"))

    def test_source_identity_and_bytes(self):
        d = self.data
        self.assertEqual(d["logicalIdentity"], "braink://volume/r4")
        self.assertEqual(d["sourceBytes"], 13050075)
        self.assertEqual(d["sourceSha256"], "5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592")
        self.assertTrue(d["twoLibraryCopiesByteIdentical"])
        self.assertRegex(d["fullManifest"]["sha256"], r"^[0-9a-f]{64}$")

    def test_vfs_and_dna_counts(self):
        self.assertEqual((self.data["vfs"]["declaredEntries"], self.data["vfs"]["verifiedEntries"]), (21, 21))
        self.assertEqual(self.data["vfs"]["totalEntryBytes"], 987623)
        self.assertFalse(self.data["vfs"]["rootHashRecomputed"])
        self.assertEqual((self.data["genomeDna"]["skillRecords"], self.data["genomeDna"]["uniqueCanonicalKeys"]), (170, 170))
        self.assertEqual((self.data["genomeDna"]["stateFamilies"], self.data["genomeDna"]["toolVolumes"]), (22, 4))

    def test_runtime_is_local_and_bounded(self):
        r = self.data["runtimeExecution"]
        self.assertEqual((r["selfTestPassed"], r["selfTestTotal"], r["exitCode"]), (12, 12, 0))
        self.assertTrue(r["predecessorPreserved"])
        self.assertFalse(r["chromiumBrowser"])
        self.assertFalse(r["v86Boot"])
        self.assertFalse(r["productionHostProcess"])
        self.assertIsNone(r["heartbeat"])
        self.assertEqual(r["externalScriptCount"], 1)

    def test_claim_boundaries(self):
        text = " ".join(self.data["claimBoundaries"]).lower()
        self.assertIn("not the separate canonical root machine", text)
        self.assertIn("not a chromium browser", text)

if __name__ == "__main__":
    unittest.main(verbosity=2)
