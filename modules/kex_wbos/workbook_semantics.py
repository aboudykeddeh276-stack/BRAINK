#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes


def _formula_dependencies(formula: str, current_sheet: str) -> list[str]:
    deps: list[str] = []
    try:
        tokens = Tokenizer(formula).items
    except Exception:
        return deps
    for token in tokens:
        if token.type == "OPERAND" and token.subtype == "RANGE":
            value = token.value.replace("$", "")
            if not value or value.startswith("["):
                continue
            if "!" not in value:
                value = f"{current_sheet}!{value}"
            if value not in deps:
                deps.append(value)
    return deps


def analyze_workbook(path: Path) -> dict[str, Any]:
    wb = load_workbook(path, read_only=False, data_only=False)
    objects: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    formulas = 0
    populated = 0

    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                if value is None:
                    continue
                populated += 1
                address = f"{ws.title}!{cell.coordinate}"
                if isinstance(value, str) and value.startswith("="):
                    formulas += 1
                    deps = _formula_dependencies(value, ws.title)
                    objects.append({
                        "objectId": f"cell://{address}",
                        "sheet": ws.title,
                        "cell": cell.coordinate,
                        "kind": "FORMULA",
                        "formula": value,
                        "dependencies": deps,
                    })
                    for dep in deps:
                        edges.append({"from": f"cell://{dep}", "to": f"cell://{address}", "relation": "FEEDS"})
                else:
                    objects.append({
                        "objectId": f"cell://{address}",
                        "sheet": ws.title,
                        "cell": cell.coordinate,
                        "kind": "VALUE",
                    })
    wb.close()

    canonical_graph = {
        "workbook": path.name,
        "sheetCount": len({obj["sheet"] for obj in objects}),
        "populatedCellCount": populated,
        "formulaCellCount": formulas,
        "objectCount": len(objects),
        "dependencyEdgeCount": len(edges),
        "objects": objects,
        "edges": edges,
    }
    canonical_graph["graphHash"] = sha256_bytes(canonical_json_bytes(canonical_graph))
    return canonical_graph


def write_semantic_index(workbook_path: Path) -> dict[str, Any]:
    graph = analyze_workbook(workbook_path)
    sidecar = workbook_path.with_suffix(workbook_path.suffix + ".semantics.json")
    atomic_write_text(sidecar, json.dumps(graph, indent=2, sort_keys=True) + "\n")
    return {
        "sidecar": sidecar.as_posix(),
        "graphHash": graph["graphHash"],
        "sheetCount": graph["sheetCount"],
        "populatedCellCount": graph["populatedCellCount"],
        "formulaCellCount": graph["formulaCellCount"],
        "objectCount": graph["objectCount"],
        "dependencyEdgeCount": graph["dependencyEdgeCount"],
    }
