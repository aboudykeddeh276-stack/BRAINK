"""
Tests for validate_skill_package.py
=====================================
These tests validate that the skill package validator correctly:
  - passes a complete, valid skill directory
  - fails each required check individually when that requirement is violated
  - issues warnings for optional checks
  - is deterministic (same input → same output)
  - correctly self-validates this package (the methodology package itself)

All tests use only the Python stdlib and temporary directories.
No GitHub network access is required.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Make the src module importable from the tests/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from validate_skill_package import run_validation  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_skill_dir(tmp: Path, identifier: str = "EXAMPLE_VALID_SKILL") -> Path:
    """Create a minimal valid skill directory under tmp."""
    skill_dir = tmp / identifier
    (skill_dir / "src").mkdir(parents=True)
    (skill_dir / "tests").mkdir(parents=True)

    (skill_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")

    (skill_dir / "manifest.json").write_text(
        json.dumps({
            "canonical_identifier": identifier,
            "version": "1.0.0",
            "purpose": "Example skill for testing.",
            "claim_boundary": {"example_capability_implemented": True},
        }),
        encoding="utf-8",
    )

    (skill_dir / "SKILL.md").write_text(
        "## Purpose\nDoes something.\n\n## Invariants\nNone.\n\n## Assumptions\nNone.\n",
        encoding="utf-8",
    )

    (skill_dir / "src" / "example.py").write_text(
        "# Example implementation\n", encoding="utf-8"
    )

    (skill_dir / "tests" / "test_example.py").write_text(
        "import unittest\n\nclass T(unittest.TestCase):\n    def test_pass(self): pass\n",
        encoding="utf-8",
    )

    return skill_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class ValidSkillPackageTests(unittest.TestCase):

    def test_complete_valid_package_passes_all_required_checks(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["verdict"], "SKILL_PACKAGE_VALID")
        failed = [c for c in report["checks"] if c["result"] == "FAIL"]
        self.assertEqual(failed, [], msg=f"Unexpected failures: {failed}")

    def test_determinism_same_input_produces_same_output(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            report1, exit1 = run_validation(skill_dir)
            report2, exit2 = run_validation(skill_dir)
        self.assertEqual(exit1, exit2)
        self.assertEqual(report1["verdict"], report2["verdict"])
        for c1, c2 in zip(report1["checks"], report2["checks"]):
            self.assertEqual(c1["result"], c2["result"])
            self.assertEqual(c1["id"], c2["id"])


class MissingRequiredFilesTests(unittest.TestCase):

    def test_missing_skill_md_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "SKILL.md").unlink()
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["verdict"], "SKILL_PACKAGE_INVALID")
        check = next(c for c in report["checks"] if c["id"] == "REQUIRED_FILES_ARE_PRESENT")
        self.assertEqual(check["result"], "FAIL")
        self.assertIn("SKILL.md", check["finding"])

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "manifest.json").unlink()
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_missing_version_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "VERSION").unlink()
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)


class InvalidManifestTests(unittest.TestCase):

    def test_invalid_json_in_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(c for c in report["checks"] if c["id"] == "MANIFEST_IS_VALID_JSON")
        self.assertEqual(check["result"], "FAIL")

    def test_missing_canonical_identifier_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            del manifest["canonical_identifier"]
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(c for c in report["checks"] if c["id"] == "MANIFEST_CONTAINS_REQUIRED_FIELDS")
        self.assertEqual(check["result"], "FAIL")

    def test_missing_purpose_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            del manifest["purpose"]
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_missing_claim_boundary_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            del manifest["claim_boundary"]
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)


class CanonicalIdentifierTests(unittest.TestCase):

    def test_lowercase_identifier_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["canonical_identifier"] = "example_lowercase_skill"
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(
            c for c in report["checks"]
            if c["id"] == "CANONICAL_IDENTIFIER_IS_SEMANTICALLY_STABLE"
        )
        self.assertEqual(check["result"], "FAIL")

    def test_empty_identifier_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["canonical_identifier"] = ""
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_identifier_with_hyphens_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["canonical_identifier"] = "EXAMPLE-HYPHENATED-SKILL"
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)


class VersionConsistencyTests(unittest.TestCase):

    def test_version_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "VERSION").write_text("2.0.0\n", encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(
            c for c in report["checks"]
            if c["id"] == "VERSION_FILE_MATCHES_MANIFEST_VERSION"
        )
        self.assertEqual(check["result"], "FAIL")
        self.assertIn("2.0.0", check["finding"])
        self.assertIn("1.0.0", check["finding"])


class SkillMdHeadingTests(unittest.TestCase):

    def test_missing_purpose_heading_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "SKILL.md").write_text(
                "## Invariants\nNone.\n\n## Assumptions\nNone.\n",
                encoding="utf-8",
            )
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(
            c for c in report["checks"]
            if c["id"] == "SKILL_MD_CONTAINS_REQUIRED_SECTION_HEADINGS"
        )
        self.assertEqual(check["result"], "FAIL")
        self.assertIn("## Purpose", check["finding"])

    def test_missing_invariants_heading_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "SKILL.md").write_text(
                "## Purpose\nDoes something.\n\n## Assumptions\nNone.\n",
                encoding="utf-8",
            )
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_missing_assumptions_heading_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "SKILL.md").write_text(
                "## Purpose\nDoes something.\n\n## Invariants\nNone.\n",
                encoding="utf-8",
            )
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)


class ClaimBoundaryTests(unittest.TestCase):

    def test_empty_claim_boundary_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["claim_boundary"] = {}
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_null_claim_value_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["claim_boundary"] = {"some_claim": None}
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(
            c for c in report["checks"]
            if c["id"] == "CLAIM_BOUNDARY_IS_EXPLICIT_AND_BOOLEAN"
        )
        self.assertEqual(check["result"], "FAIL")

    def test_string_claim_value_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["claim_boundary"] = {"some_claim": "not implemented"}
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_boolean_false_is_acceptable(self):
        """A claim set to false is explicit. It should not fail the check."""
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["claim_boundary"] = {
                "feature_a_implemented": True,
                "feature_b_implemented": False,
            }
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 0)


class ExecutableSourceTests(unittest.TestCase):

    def test_missing_src_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            import shutil
            shutil.rmtree(skill_dir / "src")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)
        check = next(
            c for c in report["checks"]
            if c["id"] == "SRC_DIRECTORY_CONTAINS_AT_LEAST_ONE_PYTHON_FILE"
        )
        self.assertEqual(check["result"], "FAIL")

    def test_empty_src_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "src" / "example.py").unlink()
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_missing_tests_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            import shutil
            shutil.rmtree(skill_dir / "tests")
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)

    def test_empty_tests_directory_fails(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            skill_dir = _make_valid_skill_dir(Path(tmp_str))
            (skill_dir / "tests" / "test_example.py").unlink()
            report, exit_code = run_validation(skill_dir)
        self.assertEqual(exit_code, 1)


class StrictModeTests(unittest.TestCase):

    def test_strict_mode_fails_on_identifier_directory_mismatch(self):
        """Directory name differs from canonical_identifier → warning → failure in strict mode."""
        with tempfile.TemporaryDirectory() as tmp_str:
            # Create a valid package whose directory is named EXAMPLE_VALID_SKILL
            # but whose canonical_identifier is set to DIFFERENT_IDENTIFIER_VALUE.
            # This produces a warning in the optional directory-name check.
            skill_dir = _make_valid_skill_dir(Path(tmp_str), identifier="EXAMPLE_VALID_SKILL")
            manifest = json.loads((skill_dir / "manifest.json").read_text())
            manifest["canonical_identifier"] = "DIFFERENT_IDENTIFIER_VALUE"
            (skill_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report_normal, exit_normal = run_validation(skill_dir, strict=False)
            report_strict, exit_strict = run_validation(skill_dir, strict=True)
        # Normal mode: should pass (mismatch is only a warning)
        self.assertEqual(exit_normal, 0)
        # Strict mode: should fail because the warning becomes a failure
        self.assertEqual(exit_strict, 1)


class SelfValidationTests(unittest.TestCase):

    def test_this_methodology_package_validates_itself(self):
        """
        The methodology skill package must pass its own validator.
        This test is the baseline evidence that the methodology is self-consistent.
        """
        methodology_dir = Path(__file__).resolve().parent.parent
        report, exit_code = run_validation(methodology_dir)
        self.assertEqual(
            exit_code,
            0,
            msg=(
                "The KEDDEH_SYSTEMS methodology skill package failed its own validator.\n"
                + json.dumps(
                    [c for c in report["checks"] if c["result"] != "PASS"],
                    indent=2,
                )
            ),
        )
        self.assertEqual(report["verdict"], "SKILL_PACKAGE_VALID")


if __name__ == "__main__":
    unittest.main()
