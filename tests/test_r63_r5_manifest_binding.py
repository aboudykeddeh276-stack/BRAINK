"""R63 exact-byte verification of the R5 standalone/cross-work manifest binding.

Architect/source authority: A. Keddeh.
Canonical architecture: KS-BRAINK-IL-LLM.
The ZIP contains exact source bytes; no historical source is overwritten.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs/estate/source-copies/r5/R63_R5_MANIFEST_SOURCE_COPIES.zip"
R5_NAME = "BRAINK_R5_SYSTEM_MANIFEST.json"
CROSS_NAME = "BRAINK_R5_SYSTEM_MANIFEST_CROSS_WORK_R1.json"
R5_SHA256 = "a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc"
R5_PARENT_SHA256 = "9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede"
R4_PARENT_SHA256 = "5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592"

class R5ManifestBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(BUNDLE) as z:
            bad = z.testzip()
            if bad:
                raise AssertionError(f"ZIP CRC failure: {bad}")
            cls.names = set(z.namelist())
            cls.r5_bytes = z.read(R5_NAME)
            cls.cross_bytes = z.read(CROSS_NAME)
        cls.r5 = json.loads(cls.r5_bytes)
        cls.cross = json.loads(cls.cross_bytes)

    def test_bundle_contains_only_the_two_canonical_source_copies(self):
        self.assertEqual(self.names, {R5_NAME, CROSS_NAME})

    def test_standalone_manifest_exact_bytes_and_identity(self):
        self.assertEqual(len(self.r5_bytes), 32546)
        self.assertEqual(hashlib.sha256(self.r5_bytes).hexdigest(), R5_SHA256)
        self.assertEqual(self.r5["identity"], "braink://volume/r5/system-orchestrator")
        self.assertEqual(self.r5["schema"], "kex.braink.executable-resident-system-enclave.r5")

    def test_cross_work_manifest_binds_standalone_manifest_hash(self):
        binding = self.cross["parent_system_orchestrator"]
        self.assertEqual(binding["identity"], self.r5["identity"])
        self.assertEqual(binding["manifest_sha256"], hashlib.sha256(self.r5_bytes).hexdigest())
        self.assertEqual(binding["manifest_sha256"], R5_SHA256)
        self.assertEqual(binding["sha256"], R5_PARENT_SHA256)

    def test_standalone_manifest_preserves_r4_parent_identity(self):
        parent = self.r5["parent"]
        self.assertEqual(parent["identity"], "braink://volume/r4")
        self.assertEqual(parent["bytes"], 13050075)
        self.assertEqual(parent["sha256"], R4_PARENT_SHA256)

    def test_manifest_surface_counts_and_descendant_identity(self):
        self.assertEqual(len(self.r5["tool_volumes"]), 4)
        self.assertEqual(len(self.r5["system_volumes"]), 15)
        self.assertEqual(len(self.r5["runtime_resources"]), 5)
        self.assertEqual(len(self.r5["workbooks"]), 3)
        self.assertEqual(len(self.r5["unified_surfaces"]), 2)
        self.assertEqual(len(self.r5["relations"]), 23)
        self.assertEqual(self.cross["identity"], "braink://volume/r5/system-orchestrator/cross-work-r1")
        self.assertNotEqual(self.cross["identity"], self.r5["identity"])
        self.assertEqual(len(self.cross["relations"]), 32)

if __name__ == "__main__":
    unittest.main(verbosity=2)
