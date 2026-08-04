#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".cpp", ".cc", ".c", ".hpp", ".h", ".swift", ".rs", ".go"}
TEST_MARKERS = ("test_", "_test.", "Tests/", "/tests/")
EVIDENCE_TERMS = {"receipt", "readback", "ledger", "evidence", "handoff", "manifest", "sha256"}
STATE_TERMS = {"state", "status", "transition", "promotion", "degraded", "failed", "recovery"}
SIDE_EFFECT_TERMS = {"write_text", "open", "mkdir", "unlink", "replace", "subprocess", "socket", "sqlite3", "requests", "urlopen"}


@dataclass(frozen=True)
class FunctionRecord:
    path: str
    language: str
    qualified_name: str
    kind: str
    line_start: int
    line_end: int
    parameters: list[str]
    return_annotation: str
    docstring_present: bool
    branch_points: int
    calls: list[str]
    imports: list[str]
    evidence_terms: list[str]
    state_terms: list[str]
    side_effect_terms: list[str]
    is_test: bool
    paired_test_files: list[str]
    testability_state: str


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def language_for(path: Path) -> str:
    return {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
        ".cpp": "C++", ".cc": "C++", ".c": "C", ".hpp": "C++", ".h": "C/C++", ".swift": "Swift",
        ".rs": "Rust", ".go": "Go",
    }.get(path.suffix, "Unknown")


def is_test_path(path: Path) -> bool:
    text = path.as_posix()
    return any(marker in text for marker in TEST_MARKERS)


def paired_tests(root: Path, source: Path, test_files: list[Path]) -> list[str]:
    stem = source.stem.removeprefix("keddeh_")
    candidates = []
    for test in test_files:
        name = test.stem.removeprefix("test_").removesuffix("_test")
        if stem == name or stem in name or name in stem:
            candidates.append(str(test.relative_to(root)))
    return sorted(candidates)


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def python_records(root: Path, path: Path, test_files: list[Path]) -> list[FunctionRecord]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    records: list[FunctionRecord] = []
    class_stack: list[str] = []

    def visit_body(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                class_stack.append(node.name)
                visit_body(node.body)
                class_stack.pop()
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = sorted({dotted_name(n.func) for n in ast.walk(node) if isinstance(n, ast.Call) and dotted_name(n.func)})
                names = {n.id.lower() for n in ast.walk(node) if isinstance(n, ast.Name)} | {n.attr.lower() for n in ast.walk(node) if isinstance(n, ast.Attribute)}
                params = [arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]]
                if node.args.vararg:
                    params.append("*" + node.args.vararg.arg)
                if node.args.kwarg:
                    params.append("**" + node.args.kwarg.arg)
                qname = ".".join([*class_stack, node.name])
                pairings = paired_tests(root, path, test_files) if not is_test_path(path) else []
                records.append(FunctionRecord(
                    path=str(path.relative_to(root)), language="Python", qualified_name=qname,
                    kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else ("method" if class_stack else "function"),
                    line_start=node.lineno, line_end=getattr(node, "end_lineno", node.lineno), parameters=params,
                    return_annotation=ast.unparse(node.returns) if node.returns else "", docstring_present=bool(ast.get_docstring(node)),
                    branch_points=sum(isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match, ast.BoolOp, ast.IfExp)) for n in ast.walk(node)),
                    calls=calls, imports=sorted(i for i in imports if i),
                    evidence_terms=sorted(EVIDENCE_TERMS & names), state_terms=sorted(STATE_TERMS & names),
                    side_effect_terms=sorted(term for term in SIDE_EFFECT_TERMS if any(term in call.lower() for call in calls)),
                    is_test=is_test_path(path) or node.name.startswith("test_"), paired_test_files=pairings,
                    testability_state="TEST" if is_test_path(path) or node.name.startswith("test_") else ("PAIRED" if pairings else "UNPAIRED"),
                ))
                visit_body(node.body)
    visit_body(tree.body)
    return records


def non_python_summary(root: Path, path: Path, test_files: list[Path]) -> FunctionRecord:
    text = path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    pairings = paired_tests(root, path, test_files) if not is_test_path(path) else []
    return FunctionRecord(
        path=str(path.relative_to(root)), language=language_for(path), qualified_name="<file-surface>", kind="file_surface",
        line_start=1, line_end=max(1, len(text.splitlines())), parameters=[], return_annotation="", docstring_present=False,
        branch_points=sum(lower.count(token) for token in (" if ", " switch ", " match ", " case ", " for ", " while ")),
        calls=[], imports=[], evidence_terms=sorted(t for t in EVIDENCE_TERMS if t in lower),
        state_terms=sorted(t for t in STATE_TERMS if t in lower), side_effect_terms=sorted(t for t in SIDE_EFFECT_TERMS if t in lower),
        is_test=is_test_path(path), paired_test_files=pairings,
        testability_state="TEST" if is_test_path(path) else ("PAIRED" if pairings else "UNPAIRED"),
    )


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def analyze(root: Path, emit: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    source_files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in SOURCE_EXTENSIONS and ".git" not in p.parts)
    test_files = [p for p in source_files if is_test_path(p)]
    records: list[FunctionRecord] = []
    parse_errors: list[dict[str, str]] = []
    for path in source_files:
        try:
            records.extend(python_records(root, path, test_files) if path.suffix == ".py" else [non_python_summary(root, path, test_files)])
        except (SyntaxError, OSError, UnicodeError) as exc:
            parse_errors.append({"path": str(path.relative_to(root)), "error": str(exc)})
    production = [r for r in records if not r.is_test]
    tests = [r for r in records if r.is_test]
    unpaired = [r for r in production if r.testability_state == "UNPAIRED"]
    side_effecting = [r for r in production if r.side_effect_terms]
    evidence_aware = [r for r in production if r.evidence_terms]
    stateful = [r for r in production if r.state_terms]
    summary = {
        "analysis_id": "analysis://keddeh/codebase-functions/v1",
        "source_files": len(source_files), "function_surfaces": len(records), "production_functions": len(production),
        "test_functions": len(tests), "unpaired_production_functions": len(unpaired),
        "side_effecting_functions": len(side_effecting), "evidence_aware_functions": len(evidence_aware),
        "state_aware_functions": len(stateful), "parse_errors": len(parse_errors),
        "test_pairing_ratio": round((len(production) - len(unpaired)) / len(production), 4) if production else 1.0,
        "global_stop": False,
    }
    payload = {"summary": summary, "records": [asdict(r) for r in records], "parse_errors": parse_errors}
    payload["analysis_sha256"] = canonical_hash(payload)
    if emit:
        out = root / "evidence" / "codebase_analysis"
        out.mkdir(parents=True, exist_ok=True)
        (out / "function_inventory.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_csv(out / "function_inventory.csv", [asdict(r) for r in records])
        write_csv(out / "unpaired_functions.csv", [asdict(r) for r in unpaired])
        report = ["# KEDDEH Codebase Functional Analysis", "", "## Summary", ""]
        report += [f"- {key}: `{value}`" for key, value in summary.items()]
        report += ["", "## Highest branch-point functions", ""]
        for record in sorted(production, key=lambda r: r.branch_points, reverse=True)[:25]:
            report.append(f"- `{record.path}::{record.qualified_name}` — branches `{record.branch_points}`, tests `{record.testability_state}`")
        report += ["", "## Unpaired production surfaces", ""]
        report += [f"- `{r.path}::{r.qualified_name}`" for r in unpaired[:100]] or ["- None"]
        (out / "FUNCTIONAL_ANALYSIS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    result = analyze(Path(args.root), emit=args.emit)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0 if result["summary"]["parse_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
