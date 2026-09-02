#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from illlm_recursive_runtime import ILLLMNode, RecursiveILLLMRuntime, TraversalEdge, _tokens
from workbook_semantics import analyze_workbook

_SAFE = re.compile(r"[^a-z0-9._~-]+")


def _segment(value: str) -> str:
    raw = value.strip().lower()
    cooked = _SAFE.sub("-", raw).strip("-")
    if cooked:
        return cooked[:80]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _workbook_root(path: Path, graph_hash: str) -> str:
    return f"il-llm://workbook/{_segment(path.name)}/{graph_hash[:16]}"


def _sheet_id(root: str, sheet: str) -> str:
    return f"{root}/sheet/{_segment(sheet)}"


def _object_id(root: str, object_id: str) -> str:
    digest = hashlib.sha256(object_id.encode("utf-8")).hexdigest()[:20]
    return f"{root}/object/{digest}"


def hydrate_workbook_into_illlm(
    runtime: RecursiveILLLMRuntime,
    workbook_path: Path,
    *,
    execution_routes: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Hydrate static workbook structure into the resident IL-LLM graph.

    This bridge preserves workbook/sheet/cell/range/formula provenance and
    formula dependency edges. It does not execute formulas, VBA, external links
    or infer executable authority from formula text. Optional execution routes
    must be supplied explicitly by the caller and are keyed by workbook
    semantic `objectId`.
    """

    graph = analyze_workbook(workbook_path)
    routes = execution_routes or {}
    root = _workbook_root(workbook_path, str(graph["graphHash"]))

    runtime.register_node(ILLLMNode(
        identity=root,
        role="WORKBOOK_SUBSTRATE",
        parent=runtime.META_ROOT,
        semantic_terms=_tokens([
            "workbook", workbook_path.name, "spreadsheet", "formula", "table",
            "structured data", "dependency graph", "machine traversable",
        ]),
        mathematical_state={
            "sheetCount": graph["sheetCount"],
            "populatedCellCount": graph["populatedCellCount"],
            "formulaCellCount": graph["formulaCellCount"],
            "dependencyEdgeCount": graph["dependencyEdgeCount"],
            "cycleCount": graph["cycleCount"],
        },
        proof_refs=(f"sha256:{graph['graphHash']}",),
        carrier=workbook_path.as_posix(),
        observed_state="STATIC_SEMANTICS_RESIDENT",
        metadata={
            "workbook": workbook_path.name,
            "semanticGraphHash": graph["graphHash"],
            "claimBoundary": graph["claimBoundary"],
        },
    ))

    sheet_ids: dict[str, str] = {}
    for item in graph["objects"]:
        sheet = str(item.get("sheet", ""))
        if not sheet or sheet in sheet_ids:
            continue
        identity = _sheet_id(root, sheet)
        runtime.register_node(ILLLMNode(
            identity=identity,
            role="WORKBOOK_SHEET",
            parent=root,
            semantic_terms=_tokens(["workbook sheet", sheet, workbook_path.name]),
            carrier=workbook_path.as_posix(),
            observed_state="STATIC_SEMANTICS_RESIDENT",
            metadata={"sheet": sheet},
        ))
        sheet_ids[sheet] = identity

    object_map: dict[str, str] = {}
    for item in graph["objects"]:
        source_object_id = str(item["objectId"])
        identity = _object_id(root, source_object_id)
        object_map[source_object_id] = identity
        sheet = str(item.get("sheet", ""))
        parent = sheet_ids.get(sheet, root)
        kind = str(item.get("kind", "OBJECT"))
        explicit_routes = tuple(routes.get(source_object_id, ()))
        semantic_values = [
            "workbook object", workbook_path.name, sheet, str(item.get("cell", "")),
            str(item.get("range", "")), kind, str(item.get("formula", "")),
        ]
        runtime.register_node(ILLLMNode(
            identity=identity,
            role=f"WORKBOOK_{kind}",
            parent=parent,
            semantic_terms=_tokens(semantic_values),
            mathematical_state={
                "cellCount": item.get("cellCount"),
                "expanded": item.get("expanded"),
                "dependencyCount": len(item.get("dependencies", [])),
                "rangeDependencyCount": len(item.get("rangeDependencies", [])),
            },
            execution_routes=explicit_routes,
            proof_refs=(f"sha256:{graph['graphHash']}",),
            carrier=workbook_path.as_posix(),
            observed_state="STATIC_SEMANTICS_RESIDENT",
            metadata={
                "sourceObjectId": source_object_id,
                "sheet": sheet or None,
                "cell": item.get("cell"),
                "range": item.get("range"),
                "formula": item.get("formula"),
                "dependencies": item.get("dependencies", []),
                "rangeDependencies": item.get("rangeDependencies", []),
            },
        ))

    # Dependency edges may originate from blank/unmaterialised cells. Preserve
    # them as explicit reference nodes instead of dropping the relation.
    def ensure_reference(source_object_id: str) -> str:
        existing = object_map.get(source_object_id)
        if existing:
            return existing
        identity = _object_id(root, source_object_id)
        object_map[source_object_id] = identity
        sheet = ""
        raw = source_object_id
        if raw.startswith("cell://"):
            tail = raw[len("cell://"):]
            sheet = tail.split("!", 1)[0] if "!" in tail else ""
        parent = sheet_ids.get(sheet, root)
        runtime.register_node(ILLLMNode(
            identity=identity,
            role="WORKBOOK_REFERENCE",
            parent=parent,
            semantic_terms=_tokens(["workbook reference", source_object_id, sheet]),
            proof_refs=(f"sha256:{graph['graphHash']}",),
            carrier=workbook_path.as_posix(),
            observed_state="REFERENCED_NOT_POPULATED",
            metadata={"sourceObjectId": source_object_id, "sheet": sheet or None},
        ))
        return identity

    edges_added = 0
    for edge in graph["edges"]:
        source = ensure_reference(str(edge["from"]))
        target = ensure_reference(str(edge["to"]))
        runtime.add_edge(TraversalEdge(
            source=source,
            target=target,
            relation=f"WORKBOOK_{edge['relation']}",
            cost=0.25,
        ))
        edges_added += 1

    receipt = {
        "schema": "kex.illlm.workbook-hydration.v1",
        "status": "HYDRATED",
        "workbook": workbook_path.name,
        "carrier": workbook_path.as_posix(),
        "workbookRoot": root,
        "semanticGraphHash": graph["graphHash"],
        "sheetCount": len(sheet_ids),
        "semanticObjectCount": len(graph["objects"]),
        "runtimeObjectCount": len(object_map),
        "dependencyEdgesAdded": edges_added,
        "runtimeGeneration": runtime.generation,
        "runtimeGraphHash": runtime.graph_hash(),
        "claimBoundary": "Workbook hydration proves static machine-traversable structure in the resident IL-LLM graph. It does not execute formulas/macros or infer actuator authority from spreadsheet content.",
    }
    receipt["receiptHash"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt
