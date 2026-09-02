from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.keddeh_unified_codebase_runtime import (
    FAILED_BOUNDED,
    SKIPPED_DEPENDENCY,
    SUCCESS,
    CONTINUED,
    dependency_order,
    run_all,
    validate_registry,
)

class UnifiedCodebaseRuntimeTests(unittest.TestCase):
    def write_runtime(self, root: Path, name: str, exit_code: int = 0) -> Path:
        script = root / f"{name}.py"
        script.write_text(
            "from pathlib import Path\n"
            f"Path('{name}.receipt.json').write_text('{{\"state\":\"written\"}}\\n')\n"
            f"raise SystemExit({exit_code})\n",
            encoding="utf-8",
        )
        return script

    def registry(self, root: Path, second_exit: int = 0) -> Path:
        first = self.write_runtime(root, "first", 0)
        second = self.write_runtime(root, "second", second_exit)
        payload = {
            "registry_id": "registry://test/runtime",
            "version": "1.0.0",
            "global_stop": False,
            "runtimes": [
                {
                    "runtime_id": "runtime://test/first",
                    "domain": "test",
                    "command": ["python3", str(first)],
                    "depends_on": [],
                    "criticality": "CORE_MANDATORY",
                    "timeout_seconds": 10,
                    "expected_artifacts": ["first.receipt.json"],
                    "supplied_capabilities": ["first"],
                },
                {
                    "runtime_id": "runtime://test/second",
                    "domain": "test",
                    "command": ["python3", str(second)],
                    "depends_on": ["runtime://test/first"],
                    "criticality": "CORE_DEGRADED",
                    "timeout_seconds": 10,
                    "expected_artifacts": ["second.receipt.json"],
                    "supplied_capabilities": ["second"],
                },
            ],
        }
        path = root / "registry.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def continuation_registry(self, root: Path) -> Path:
        bootstrap = root / "bootstrap.py"
        bootstrap.write_text(
            "import json\nfrom pathlib import Path\n"
            "Path('bootstrap.receipt.json').write_text('{}')\n"
            "p=Path('handoff.json'); p.write_text(json.dumps({'state':'VERIFIED','next_operation':'advance','proof':'p0','current_machine':{'generation':0}}))\n",
            encoding="utf-8",
        )
        continuation = root / "continue.py"
        continuation.write_text(
            "import json\nfrom pathlib import Path\n"
            "p=Path('handoff.json'); h=json.loads(p.read_text()); g=int(h['current_machine']['generation'])+1\n"
            "Path('continued.receipt.json').write_text(json.dumps({'generation':g}))\n"
            "p.write_text(json.dumps({'state':'VERIFIED','next_operation':'advance','proof':f'p{g}','current_machine':{'generation':g}}))\n",
            encoding="utf-8",
        )
        payload = {
            "registry_id": "registry://test/continuation",
            "version": "1.0.0",
            "global_stop": False,
            "runtimes": [{
                "runtime_id": "runtime://test/recursive",
                "domain": "test",
                "command": ["python3", str(bootstrap)],
                "depends_on": [],
                "criticality": "CORE_MANDATORY",
                "timeout_seconds": 10,
                "expected_artifacts": ["bootstrap.receipt.json", "handoff.json"],
                "supplied_capabilities": ["recursive"],
                "continuation": {
                    "handoff_path": "handoff.json",
                    "command": ["python3", str(continuation)],
                    "max_steps": 3,
                    "expected_artifacts": ["continued.receipt.json", "handoff.json"],
                    "state_field": "state",
                    "executable_state": "VERIFIED",
                    "operation_field": "next_operation",
                    "executable_operation": "advance",
                },
            }],
        }
        path = root / "continuation-registry.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_dependency_order(self) -> None:
        runtimes = [{"runtime_id": "b", "depends_on": ["a"]}, {"runtime_id": "a", "depends_on": []}]
        self.assertEqual([item["runtime_id"] for item in dependency_order(runtimes)], ["a", "b"])

    def test_registry_rejects_unknown_dependency(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtime_unknown_dependencies"):
            validate_registry({"runtimes": [{"runtime_id": "a", "domain": "x", "command": ["true"], "depends_on": ["missing"], "criticality": "CORE_DEGRADED", "timeout_seconds": 1, "expected_artifacts": [], "supplied_capabilities": []}]})

    def test_registry_rejects_incomplete_continuation(self) -> None:
        with self.assertRaisesRegex(ValueError, "continuation_missing_fields"):
            validate_registry({"runtimes": [{"runtime_id": "a", "domain": "x", "command": ["true"], "depends_on": [], "criticality": "CORE_DEGRADED", "timeout_seconds": 1, "expected_artifacts": [], "supplied_capabilities": [], "continuation": {"command": ["true"]}}]})

    def test_successful_runtime_chain_writes_receipt_and_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_all(root, self.registry(root), emit_receipt=True)
            self.assertEqual(payload["receipt"]["runtimes_succeeded"], 2)
            self.assertEqual(payload["receipt"]["overall_state"], "OPERATIONAL")
            self.assertTrue(payload["receipt"]["ledger_readback_passed"])
            self.assertTrue((root / "evidence/unified_codebase_runtime_receipt.json").is_file())

    def test_failure_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_all(root, self.registry(root, second_exit=3), emit_receipt=True)
            states = {item["runtime_id"]: item["state"] for item in payload["runtime_results"]}
            self.assertEqual(states["runtime://test/first"], SUCCESS)
            self.assertEqual(states["runtime://test/second"], FAILED_BOUNDED)
            self.assertEqual(payload["receipt"]["overall_state"], "OPERATIONAL_DEGRADED")
            self.assertFalse(payload["receipt"]["global_stop"])

    def test_failed_dependency_skips_only_dependent_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = json.loads(self.registry(root).read_text())
            registry["runtimes"][0]["command"] = ["python3", "-c", "raise SystemExit(1)"]
            path = root / "registry-failure.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            payload = run_all(root, path, emit_receipt=True)
            states = {item["runtime_id"]: item["state"] for item in payload["runtime_results"]}
            self.assertEqual(states["runtime://test/first"], FAILED_BOUNDED)
            self.assertEqual(states["runtime://test/second"], SKIPPED_DEPENDENCY)
            self.assertFalse(payload["receipt"]["global_stop"])

    def test_executable_handoff_is_followed_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = run_all(root, self.continuation_registry(root), emit_receipt=True)
            result = payload["runtime_results"][0]
            self.assertEqual(result["state"], SUCCESS)
            self.assertEqual(result["continuation_state"], CONTINUED)
            self.assertEqual(result["continuation_steps"], 3)
            self.assertEqual(payload["receipt"]["continuation_steps_executed"], 3)
            self.assertEqual(json.loads((root / "handoff.json").read_text())["current_machine"]["generation"], 3)
            self.assertEqual(len(result["continuation_receipts"]), 3)
            self.assertTrue(payload["receipt"]["ledger_readback_passed"])

if __name__ == "__main__":
    unittest.main()
