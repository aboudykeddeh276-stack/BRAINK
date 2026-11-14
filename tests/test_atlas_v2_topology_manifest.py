#!/usr/bin/env python3
"""Checks the topology-snapshot supplement manifest without requiring source workbooks."""
import json
import re
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "docs" / "estate" / "ATLAS_V2_TOPOLOGY_SNAPSHOT_SUPPLEMENT_20261002.manifest.json"

class TopologySupplementManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PATH.read_text(encoding="utf-8"))

    def test_source_and_snapshot_identity(self):
        d = self.data
        self.assertEqual(d["schema"], "KS-BRAINK-IL-LLM/topology-snapshot-supplement-manifest/1")
        self.assertEqual(d["snapshotDate"], "2026-10-02")
        self.assertEqual(d["source"]["sha256"], "1d0873c355ff764ea896fb69d0ad39d0eb93bccf41ccb464078cd9b49496b050")

    def test_registry_counts(self):
        c = self.data["counts"]
        self.assertEqual((c["r5Identities"], c["p11LogicalObjects"], c["p11UniqueCarriers"]), (33, 76, 95))
        self.assertEqual((c["multiCarrierObjects"], c["relations"], c["mechanicsRecords"]), (19, 32, 14))
        self.assertEqual((c["evidenceBoundaries"], c["defects"], c["r5CurrentSnapshotIdentities"]), (10, 2, 33))

    def test_artifact_hashes_and_inventory_digest(self):
        s = self.data["supplement"]
        self.assertGreater(s["uncompressedBytes"], s["compressedBytes"])
        self.assertRegex(s["uncompressedSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(s["compressedSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.data["crossSnapshotCarrierRowsIdentical"], 95)
        self.assertRegex(self.data["carrierInventoryCanonicalRowSha256"], r"^[0-9a-f]{64}$")

    def test_identity_divergence_is_preserved(self):
        d = self.data["identityVersionDivergence"]
        self.assertEqual(d["current"], "braink://volume/r5/system-orchestrator")
        self.assertEqual(d["snapshot20261002"], "braink://volume/r5/system-orchestrator/cross-work-r1")
        self.assertFalse(d["equivalenceOrAliasInferred"])

    def test_root_bytes_are_a_two_carrier_sum(self):
        r = self.data["rootCarrierAccounting"]
        self.assertEqual(r["htmlCarrierBytes"] + r["jsonArchitectureRootCarrierBytes"], r["logicalObjectTotalBytes"])
        self.assertEqual(r["logicalObjectTotalBytes"], 3748432)

if __name__ == "__main__":
    unittest.main(verbosity=2)
