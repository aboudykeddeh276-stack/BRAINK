"""
Tests for ci_failure_investigator.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from ci_failure_investigator import _classify_failure, _extract_failure_line


class ClassifyFailureTests(unittest.TestCase):

    def test_missing_file_classified(self):
        log = "tee: evidence/report.json: No such file or directory"
        cls, hint = _classify_failure(log)
        self.assertEqual(cls, "MISSING_FILE_OR_DIRECTORY")
        self.assertIn("mkdir", hint)

    def test_syntax_error_classified(self):
        log = "SyntaxError: invalid syntax (script.py, line 42)"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "SYNTAX_ERROR_IN_SOURCE")

    def test_test_assertion_classified(self):
        log = "AssertionError: False is not true"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "TEST_ASSERTION_FAILED")

    def test_module_not_found_classified(self):
        log = "ModuleNotFoundError: No module named 'requests'"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "DEPENDENCY_NOT_INSTALLED")

    def test_permission_denied_classified(self):
        log = "Permission denied: /etc/shadow"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "PERMISSION_DENIED")

    def test_timeout_classified(self):
        log = "Operation timed out after 300 seconds"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "TIMEOUT")

    def test_unknown_returns_unknown(self):
        log = "some completely unrecognised output line with no pattern"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "UNKNOWN")

    def test_returns_first_matching_class(self):
        log = "tee: evidence/file.json: No such file or directory\nSyntaxError: blah"
        cls, _ = _classify_failure(log)
        self.assertEqual(cls, "MISSING_FILE_OR_DIRECTORY")


class ExtractFailureLineTests(unittest.TestCase):

    def test_error_annotation_extracted(self):
        log = "some line\n##[error]Process completed with exit code 1.\nmore"
        line = _extract_failure_line(log)
        self.assertEqual(line, "Process completed with exit code 1.")

    def test_error_keyword_extracted_when_no_annotation(self):
        log = "running step\nError: command failed\nmore output"
        line = _extract_failure_line(log)
        self.assertIn("Error", line)

    def test_empty_log_returns_empty_string(self):
        line = _extract_failure_line("")
        self.assertEqual(line, "")


if __name__ == "__main__":
    unittest.main()
