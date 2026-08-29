from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.keddeh_codebase_function_analyzer import analyze


class CodebaseFunctionAnalyzerTests(unittest.TestCase):
    def test_analyzer_maps_functions_tests_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "alpha.py").write_text(
                "from pathlib import Path\n"
                "def execute(value: int) -> bool:\n"
                "    receipt = Path('receipt.json')\n"
                "    if value > 1:\n"
                "        receipt.write_text('ok')\n"
                "        return True\n"
                "    return False\n",
                encoding="utf-8",
            )
            (root / "tests" / "test_alpha.py").write_text(
                "def test_execute():\n    assert True\n",
                encoding="utf-8",
            )
            result = analyze(root, emit=True)
            summary = result["summary"]
            self.assertEqual(summary["parse_errors"], 0)
            self.assertGreaterEqual(summary["production_functions"], 1)
            self.assertGreaterEqual(summary["test_functions"], 1)
            self.assertEqual(summary["unpaired_production_functions"], 0)
            record = next(row for row in result["records"] if row["qualified_name"] == "execute")
            self.assertEqual(record["testability_state"], "PAIRED")
            self.assertIn("receipt", record["evidence_terms"])
            self.assertIn("write_text", record["side_effect_terms"])
            self.assertTrue((root / "evidence" / "codebase_analysis" / "function_inventory.json").is_file())

    def test_unknown_syntax_is_reported_without_global_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            result = analyze(root)
            self.assertEqual(result["summary"]["parse_errors"], 1)
            self.assertIs(result["summary"]["global_stop"], False)

    def test_analysis_hash_is_stable_for_same_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "module.py").write_text("def identity(value):\n    return value\n", encoding="utf-8")
            first = analyze(root)
            second = analyze(root)
            self.assertEqual(first["analysis_sha256"], second["analysis_sha256"])


if __name__ == "__main__":
    unittest.main()
