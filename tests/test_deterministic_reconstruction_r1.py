import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "deterministic_reconstruction_r1.py"


class DeterministicReconstructionTests(unittest.TestCase):
    def run_experiment(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_reconstruction_is_byte_field_identical(self):
        report = self.run_experiment()
        self.assertTrue(report["reconstruction"]["full_field_equality"])

    def test_roots_are_identical(self):
        report = self.run_experiment()
        self.assertTrue(report["reconstruction"]["semantic_root_equal"])
        self.assertTrue(report["reconstruction"]["envelope_root_equal"])

    def test_seed_is_strictly_smaller_than_expanded_envelope(self):
        report = self.run_experiment()
        self.assertLess(
            report["minimal_seed"]["canonical_bytes"],
            report["reference"]["canonical_bytes"],
        )

    def test_derivable_fields_are_explicit(self):
        report = self.run_experiment()
        self.assertIn("semantic_root", report["derivable_fields"])
        self.assertIn("dictionary_root", report["derivable_fields"])
        self.assertIn("ab_tokens", report["derivable_fields"])
        self.assertIn("envelope_root", report["derivable_fields"])

    def test_no_universal_compression_claim(self):
        report = self.run_experiment()
        self.assertIn("universal compression", report["claim_boundary"]["not_proven"])


if __name__ == "__main__":
    unittest.main()
