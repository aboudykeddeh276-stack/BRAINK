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


def _strongly_connected_components(edges: list[dict[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for edge in edges:
        graph.setdefault(edge["from"], set()).add(edge["to"])
        graph.setdefault(edge["to"], set())

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for nxt in sorted(graph[node]):
            if nxt not in indices:
                visit(nxt)
                lowlink[node] = min(lowlink[node], lowlink[nxt])
            elif nxt in on_stack:
                lowlink[node] = min(lowlink[node], indices[nxt])

        if lowlink[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return components


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

    components = _strongly_connected_components(edges)
    self_edges = {edge["from"] for edge in edges if edge["from"] == edge["to"]}
    cycles = [component for component in components if len(component) > 1 or any(node in self_edges for node in component)]

    canonical_graph = {
        "workbook": path.name,
        "sheetCount": len({obj["sheet"] for obj in objects}),
        "populatedCellCount": populated,
        "formulaCellCount": formulas,
        "objectCount": len(objects),
        "dependencyEdgeCount": len(edges),
        "stronglyConnectedComponentCount": len(components),
        "cycleCount": len(cycles),
        "cycles": cycles,
        "objects": objects,
        "edges": edges,
        "claimBoundary": "Dependency and cycle analysis is static formula-graph analysis. It does not execute Excel calculation, macros, volatile functions, or external links.",
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
        "cycleCount": graph["cycleCount"],
        "cycles": graph["cycles"],
    }
