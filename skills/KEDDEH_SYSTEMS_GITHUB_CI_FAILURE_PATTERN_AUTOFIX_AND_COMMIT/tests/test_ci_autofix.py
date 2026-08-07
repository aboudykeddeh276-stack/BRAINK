"""
Tests for ci_autofix.py
"""
import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from ci_autofix import _extract_missing_path, apply_fixes


class ExtractMissingPathTests(unittest.TestCase):

    def test_tee_pattern(self):
        line = "tee: evidence/persisted_export_cli_readback.json: No such file or directory"
        result = _extract_missing_path(line)
        self.assertEqual(result, "evidence")

    def test_quoted_path_pattern(self):
        line = "open 'runtime_volume/outbox/data': No such file or directory"
        result = _extract_missing_path(line)
        self.assertIsNotNone(result)

    def test_filnotfounderror_pattern(self):
        line = "FileNotFoundError: [Errno 2] No such file or directory: 'exports/downloads/file.zip'"
        result = _extract_missing_path(line)
        self.assertIsNotNone(result)

    def test_unrecognised_line_returns_none(self):
        result = _extract_missing_path("SyntaxError: invalid syntax")
        self.assertIsNone(result)


class ApplyFixesTests(unittest.TestCase):

    def _make_diagnosis(self, job_name, root_cause, failure_line):
        return {
            "failed_jobs": [{
                "job_name": job_name,
                "root_cause_class": root_cause,
                "failure_line": failure_line,
                "fix_hint": "test hint",
            }]
        }

    def test_missing_dir_fix_inserts_mkdir_into_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wf_dir = root / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            wf_content = (
                "jobs:\n"
                "  my-job:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - name: Run something\n"
                "        run: |\n"
                "          echo hello\n"
                "          tee evidence/out.json\n"
            )
            (wf_dir / "test.yml").write_text(wf_content)
            diagnosis = self._make_diagnosis(
                "my-job",
                "MISSING_FILE_OR_DIRECTORY",
                "tee: evidence/out.json: No such file or directory",
            )
            report = apply_fixes(diagnosis, root, dry_run=False)
            content = (wf_dir / "test.yml").read_text()

        applied = report["fixes_applied"]
        self.assertEqual(len(applied), 1)
        self.assertTrue(applied[0]["applied"], msg=applied[0]["change_description"])
        self.assertIn("mkdir -p evidence", content)

    def test_dry_run_does_not_write_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wf_dir = root / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            wf_content = (
                "jobs:\n"
                "  my-job:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - name: Run\n"
                "        run: |\n"
                "          echo x\n"
            )
            wf_path = wf_dir / "test.yml"
            wf_path.write_text(wf_content)
            original_content = wf_content
            diagnosis = self._make_diagnosis(
                "my-job",
                "MISSING_FILE_OR_DIRECTORY",
                "tee: outputs/report.json: No such file or directory",
            )
            apply_fixes(diagnosis, root, dry_run=True)
            content_after = wf_path.read_text()
        self.assertEqual(content_after, original_content)

    def test_non_fixable_class_goes_to_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            diagnosis = self._make_diagnosis(
                "some-job", "SYNTAX_ERROR_IN_SOURCE", "SyntaxError: invalid syntax"
            )
            report = apply_fixes(diagnosis, Path(tmp), dry_run=False)
        self.assertEqual(len(report["fixes_not_applicable"]), 1)
        self.assertEqual(len(report["fixes_applied"]), 0)


if __name__ == "__main__":
    unittest.main()
