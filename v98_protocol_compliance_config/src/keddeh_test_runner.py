#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class TestCaseReceipt:
    module: str
    test_name: str
    status: str
    detail: str


@dataclass(frozen=True)
class TestRunnerReceipt:
    version: str
    tests_discovered: int
    tests_executed: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    receipt_path: str
    timestamp: float


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_module(path: Path):
    module_name = f"keddeh_test_{path.stem}_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def discover_function_tests(test_dir: Path) -> List[tuple[Path, str, Any]]:
    discovered: List[tuple[Path, str, Any]] = []
    for path in sorted(test_dir.glob("test_*.py")):
        module = load_module(path)
        for name, obj in sorted(vars(module).items()):
            if name.startswith("test_") and callable(obj):
                discovered.append((path, name, obj))
        for _, cls in sorted(vars(module).items()):
            if inspect.isclass(cls):
                for name, method in sorted(vars(cls).items()):
                    if name.startswith("test_") and callable(method):
                        # TestCase classes are covered by unittest when called directly; this runner
                        # records them as discovered but skips bound execution to avoid double-running.
                        discovered.append((path, f"{cls.__name__}.{name}", None))
    return discovered


def run_tests(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    test_dir = root / "tests"
    evidence_dir = root / "evidence"
    started = time.time()
    cases: List[TestCaseReceipt] = []

    discovered = discover_function_tests(test_dir)
    executed = 0
    passed = 0
    failed = 0
    skipped = 0
    for path, name, fn in discovered:
        if fn is None:
            skipped += 1
            cases.append(TestCaseReceipt(str(path.relative_to(root)), name, "SKIPPED", "class_method_recorded_for_unittest"))
            continue
        signature = inspect.signature(fn)
        required = [p for p in signature.parameters.values() if p.default is inspect._empty and p.kind in {p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY}]
        if required:
            skipped += 1
            cases.append(TestCaseReceipt(str(path.relative_to(root)), name, "SKIPPED", "requires_external_fixture"))
            continue
        executed += 1
        try:
            fn()
            passed += 1
            cases.append(TestCaseReceipt(str(path.relative_to(root)), name, "PASS", "executed"))
        except Exception:
            failed += 1
            cases.append(TestCaseReceipt(str(path.relative_to(root)), name, "FAIL", traceback.format_exc(limit=5)))

    receipt_path = evidence_dir / "test_runner_receipt.json"
    receipt = TestRunnerReceipt(
        version="V99",
        tests_discovered=len(discovered),
        tests_executed=executed,
        tests_passed=passed,
        tests_failed=failed,
        tests_skipped=skipped,
        receipt_path=str(receipt_path),
        timestamp=started,
    )
    payload = {
        "receipt": asdict(receipt),
        "cases": [asdict(case) for case in cases],
        "plain_function_tests_executed": True,
        "unittest_discover_alone_would_miss_plain_functions": True,
    }
    if emit_receipt:
        write_json(receipt_path, payload)
    return payload


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = run_tests(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result["receipt"], indent=2, sort_keys=True))
    return 0 if result["receipt"]["tests_failed"] == 0 and result["receipt"]["tests_executed"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
