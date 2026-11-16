"""R63 exact-byte verification of the R5 standalone/cross-work manifest binding.

Architect/source authority: A. Keddeh.
Canonical architecture: KS-BRAINK-IL-LLM.
The standalone manifest is an exact source copy. The cross-work excerpt is
explicitly a derived binding view; the full source remains separately hashed.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
R5_PATH = ROOT / "docs/estate/source-copies/r5/BRAINK_R5_SYSTEM_MANIFEST.json"
EXCERPT_PATH = ROOT / "docs/evidence/R63_R5_CROSS_WORK_PARENT_BINDING_EXCERPT.json"
R5_SHA256 = "a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc"
R5_PARENT_SHA256 = "9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede"
R4_PARENT_SHA256 = "5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592"
CROSS_SHA256 = "5d867ae7d7f517d6cdde14c138e67e90571062521e5d912fd8812165da1ce985"

class R5ManifestBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5_bytes = R5_PATH.read_bytes()
        cls.r5 = json.loads(cls.r5_bytes)
        cls.excerpt = json.loads(EXCERPT_PATH.read_text())

    def test_standalone_manifest_exact_bytes_and_identity(self):
        self.assertEqual(len(self.r5_bytes), 32546)
        self.assertEqual(hashlib.sha256(self.r5_bytes).hexdigest(), R5_SHA256)
        self.assertEqual(self.r5["identity"], "braink://volume/r5/system-orchestrator")
        self.assertEqual(self.r5["schema"], "kex.braink.executable-resident-system-enclave.r5")

    def test_cross_work_source_identity_and_hash_are_preserved(self):
        self.assertEqual(self.excerpt["representation"], "derived_excerpt_not_full_source")
        self.assertEqual(self.excerpt["source_file"], "BRAINK_R5_SYSTEM_MANIFEST_CROSS_WORK_R1.json")
        self.assertEqual(self.excerpt["source_bytes"], 39430)
        self.assertEqual(self.excerpt["source_sha256"], CROSS_SHA256)
        self.assertEqual(self.excerpt["identity"], "braink://volume/r5/system-orchestrator/cross-work-r1")

    def test_cross_work_manifest_binds_standalone_manifest_hash(self):
        binding = self.excerpt["parent_system_orchestrator"]
        self.assertEqual(binding["identity"], self.r5["identity"])
        self.assertEqual(binding["manifest_file"], R5_PATH.name)
        self.assertEqual(binding["manifest_bytes"], len(self.r5_bytes))
        self.assertEqual(binding["manifest_sha256"], hashlib.sha256(self.r5_bytes).hexdigest())
        self.assertEqual(binding["manifest_sha256"], R5_SHA256)
        self.assertEqual(binding["sha256"], R5_PARENT_SHA256)

    def test_standalone_manifest_preserves_r4_parent_identity(self):
        parent = self.r5["parent"]
        self.assertEqual(parent["identity"], "braink://volume/r4")
        self.assertEqual(parent["bytes"], 13050075)
        self.assertEqual(parent["sha256"], R4_PARENT_SHA256)

    def test_manifest_surface_counts(self):
        self.assertEqual(len(self.r5["tool_volumes"]), 4)
        self.assertEqual(len(self.r5["system_volumes"]), 15)
        self.assertEqual(len(self.r5["runtime_resources"]), 5)
        self.assertEqual(len(self.r5["workbooks"]), 3)
        self.assertEqual(len(self.r5["unified_surfaces"]), 2)
        self.assertEqual(len(self.r5["relations"]), 23)

    def test_cross_work_descendant_is_not_the_r5_parent(self):
        self.assertNotEqual(self.excerpt["identity"], self.r5["identity"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
