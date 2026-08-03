from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from src.keddeh_test_runner import run_tests


def test_runner_supports_package_qualified_imports():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "evidence").mkdir()
        (root / "src" / "sample_runtime.py").write_text(
            "VALUE = 7\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_sample_runtime.py").write_text(
            "from src.sample_runtime import VALUE\n\n"
            "def test_package_import():\n"
            "    assert VALUE == 7\n",
            encoding="utf-8",
        )

        original_path = list(sys.path)
        try:
            result = run_tests(root, emit_receipt=True)
        finally:
            sys.path[:] = original_path

        receipt = result["receipt"]
        assert receipt["tests_discovered"] == 1
        assert receipt["tests_executed"] == 1
        assert receipt["tests_passed"] == 1
        assert receipt["tests_failed"] == 0
        assert (root / "evidence" / "test_runner_receipt.json").exists()
