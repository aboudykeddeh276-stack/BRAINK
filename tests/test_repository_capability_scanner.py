import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "repository_capability_scanner.py"
spec = importlib.util.spec_from_file_location("scanner", MODULE_PATH)
scanner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(scanner)


def test_classify_tree_detects_runtime_and_test_surface():
    tree = [
        {"type": "blob", "path": "package.json"},
        {"type": "blob", "path": "src/index.ts"},
        {"type": "blob", "path": "tests/runtime.test.ts"},
        {"type": "blob", "path": ".github/workflows/ci.yml"},
    ]
    result = scanner.classify_tree(tree)
    assert result["file_count"] == 4
    assert result["source_file_count"] == 2
    assert result["test_surface"] is True
    assert result["workflow_count"] == 1
    assert "node_manifest" in result["manifest_or_entrypoint_signals"]


def test_classify_tree_does_not_infer_execution_from_documentation():
    tree = [
        {"type": "blob", "path": "README.md"},
        {"type": "blob", "path": "docs/design.md"},
    ]
    result = scanner.classify_tree(tree)
    assert result["file_count"] == 2
    assert result["source_file_count"] == 0
    assert result["manifest_or_entrypoint_signals"] == []
    assert result["test_surface"] is False
