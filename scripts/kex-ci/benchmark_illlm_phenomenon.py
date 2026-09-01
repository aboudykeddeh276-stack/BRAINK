#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes  # noqa: E402
from illlm_context_translator import ILLLMContextTranslator, TranslationContext  # noqa: E402
from illlm_definitions import DefinitionGraph, DefinitionObject  # noqa: E402
from illlm_recursive_runtime import ILLLMNode, RecursiveILLLMRuntime, _tokens  # noqa: E402

OUT = BASE / "reports" / "kex-wbos" / "illlm-phenomenon-benchmark.json"
SECRET = "benchmark-only-il-llm-capability-secret"


def ns() -> int:
    return time.perf_counter_ns()


def median(values: list[int]) -> float:
    return float(statistics.median(values)) if values else 0.0


def p95(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)])


def synthetic_runtime(size: int, *, executable_stride: int = 17) -> RecursiveILLLMRuntime:
    runtime = RecursiveILLLMRuntime()
    root = "il-llm://global/mathematics"
    runtime.register_node(ILLLMNode(
        identity=root,
        role="MATHEMATICS",
        parent=runtime.META_ROOT,
        semantic_terms=_tokens(["mathematics", "maths", "number", "relation", "function"]),
        observed_state="RESIDENT",
    ))
    for i in range(size):
        domain = i % 97
        executable = i % executable_stride == 0
        identity = f"il-llm://global/mathematics/object/{i:08d}"
        terms = [
            "mathematics",
            f"domain-{domain}",
            f"class-{i % 13}",
            f"operator-{i % 29}",
            "target-term" if domain == 42 else "ordinary-term",
        ]
        runtime.register_node(ILLLMNode(
            identity=identity,
            role="MATHEMATICAL_OBJECT",
            parent=root,
            semantic_terms=_tokens(terms),
            mathematical_state={"ordinal": i, "domain": domain},
            execution_routes=(f"SOURCE_INGEST::KEX_MATH_{i:08d}",) if executable else (),
            observed_state="RESIDENT",
        ))
    caller = "il-llm://local/benchmark-agent"
    runtime.register_node(ILLLMNode(
        identity=caller,
        role="LOCAL_ILLLM",
        parent=runtime.META_ROOT,
        semantic_terms=_tokens(["benchmark", "local", "agent"]),
        observed_state="RESIDENT",
    ))
    return runtime


def naive_scan(runtime: RecursiveILLLMRuntime, query: str, *, within: str, require_execution: bool) -> list[str]:
    q = _tokens([query])
    permitted = runtime.descendants(within) | {within}
    scored: list[tuple[int, str]] = []
    for identity, node in runtime.nodes.items():
        if identity not in permitted:
            continue
        if require_execution and not node.execution_routes:
            continue
        overlap = len(q & node.semantic_terms)
        if overlap:
            scored.append((overlap, identity))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [identity for _, identity in scored[:8]]


def build_definition_graph(size: int, depth: int = 12) -> tuple[DefinitionGraph, str, list[DefinitionObject]]:
    graph = DefinitionGraph(max_definitions=max(1000, size + depth + 10), max_depth=max(128, depth + 4))
    objects: list[DefinitionObject] = []
    for i in range(size):
        obj = DefinitionObject(
            identity=f"definition://noise/{i:08d}",
            defines=f"subject://noise/{i:08d}",
            definition_class="NOISE",
            value={"ordinal": i},
        )
        graph.register(obj); objects.append(obj)
    subject = "subject://maths/target"
    current = subject
    for level in range(depth):
        identity = f"definition://maths/target/{level:03d}"
        obj = DefinitionObject(
            identity=identity,
            defines=current,
            definition_class="HIGHER_ORDER" if level else "PRIMARY",
            value={"level": level},
            relations=(("DEFINITION_OF", current),),
        )
        graph.register(obj); objects.append(obj)
        current = identity
    return graph, subject, objects


def naive_definition_chain(objects: list[DefinitionObject], subject: str, max_depth: int = 128) -> int:
    frontier = [subject]
    seen: set[str] = set()
    depth = 0
    while frontier and depth < max_depth:
        nxt: list[str] = []
        for current in frontier:
            if current in seen:
                continue
            seen.add(current)
            for obj in objects:
                if obj.defines == current:
                    nxt.append(obj.identity)
        frontier = nxt
        depth += 1
    return depth


def timed(fn, repeats: int) -> list[int]:
    out: list[int] = []
    for _ in range(repeats):
        start = ns(); fn(); out.append(ns() - start)
    return out


def scaling_exponent(points: list[tuple[int, float]]) -> float | None:
    clean = [(n, t) for n, t in points if n > 0 and t > 0]
    if len(clean) < 2:
        return None
    xs = [math.log(n) for n, _ in clean]
    ys = [math.log(t) for _, t in clean]
    xbar = statistics.fmean(xs); ybar = statistics.fmean(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / denom


def benchmark_size(size: int, repeats: int) -> dict[str, Any]:
    build_start = ns(); runtime = synthetic_runtime(size); cold_build = ns() - build_start
    root = "il-llm://global/mathematics"
    query = "target-term mathematics domain-42"

    naive = timed(lambda: naive_scan(runtime, query, within=root, require_execution=False), repeats)
    indexed = timed(lambda: runtime.contextual_candidates(query, within=root, require_execution=False, limit=8), repeats)

    graph, definition_subject, definition_objects = build_definition_graph(size)
    naive_defs = timed(lambda: naive_definition_chain(definition_objects, definition_subject), max(3, repeats // 5))
    indexed_defs = timed(lambda: graph.definition_chain(definition_subject), repeats)

    # Single semantic delta against an already resident estate.
    def apply_delta() -> None:
        identity = f"il-llm://global/mathematics/delta/{time.perf_counter_ns()}"
        runtime.register_node(ILLLMNode(
            identity=identity,
            role="MATHEMATICAL_OBJECT",
            parent=root,
            semantic_terms=_tokens(["mathematics", "delta", "target-term"]),
            observed_state="RESIDENT",
        ))

    delta_samples = timed(apply_delta, max(3, repeats // 5))
    rebuild_samples = timed(lambda: synthetic_runtime(size), max(3, min(7, repeats // 10 or 1)))

    translator = ILLLMContextTranslator(runtime, SECRET)
    ctx = TranslationContext(
        caller_illlm="il-llm://local/benchmark-agent",
        global_context=root,
        authority="BENCHMARK",
        query="mathematics target-term",
        require_execution=True,
        ttl_seconds=60,
    )
    translation_samples = timed(lambda: translator.translate(ctx), repeats)
    translation = translator.translate(ctx)

    naive_med = median(naive); indexed_med = median(indexed)
    naive_def_med = median(naive_defs); indexed_def_med = median(indexed_defs)
    rebuild_med = median(rebuild_samples); delta_med = median(delta_samples)
    return {
        "size": size,
        "nodeCountAfterDelta": len(runtime.nodes),
        "coldBuildNs": cold_build,
        "contextResolution": {
            "naiveMedianNs": naive_med,
            "indexedMedianNs": indexed_med,
            "indexedP95Ns": p95(indexed),
            "speedup": naive_med / max(1.0, indexed_med),
            "candidateBucket": len(runtime.term_index.get("target-term", set())),
        },
        "definitionTraversal": {
            "naiveMedianNs": naive_def_med,
            "indexedMedianNs": indexed_def_med,
            "speedup": naive_def_med / max(1.0, indexed_def_med),
            "definitionDepth": graph.definition_chain(definition_subject).get("depth"),
        },
        "incrementalMaintenance": {
            "fullRebuildMedianNs": rebuild_med,
            "singleDeltaMedianNs": delta_med,
            "speedup": rebuild_med / max(1.0, delta_med),
        },
        "intentTranslation": {
            "medianNs": median(translation_samples),
            "p95Ns": p95(translation_samples),
            "status": translation.get("status"),
            "typedAction": translation.get("typedAction"),
        },
    }


def bench(sizes: list[int], repeats: int) -> dict[str, Any]:
    results = [benchmark_size(size, repeats) for size in sizes]
    context_naive = [(r["size"], r["contextResolution"]["naiveMedianNs"]) for r in results]
    context_indexed = [(r["size"], r["contextResolution"]["indexedMedianNs"]) for r in results]
    def_naive = [(r["size"], r["definitionTraversal"]["naiveMedianNs"]) for r in results]
    def_indexed = [(r["size"], r["definitionTraversal"]["indexedMedianNs"]) for r in results]
    delta_points = [(r["size"], r["incrementalMaintenance"]["singleDeltaMedianNs"]) for r in results]
    rebuild_points = [(r["size"], r["incrementalMaintenance"]["fullRebuildMedianNs"]) for r in results]

    payload: dict[str, Any] = {
        "schema": "kex.illlm.phenomenon-benchmark.v1",
        "hypothesis": "Pre-organised recursive definitions plus resident contextual indices reduce repeated work relative to whole-estate semantic reconstruction, while delta maintenance avoids full rebuilds for local changes.",
        "sizes": sizes,
        "repeats": repeats,
        "results": results,
        "scaling": {
            "naiveContextExponent": scaling_exponent(context_naive),
            "indexedContextExponent": scaling_exponent(context_indexed),
            "naiveDefinitionExponent": scaling_exponent(def_naive),
            "indexedDefinitionExponent": scaling_exponent(def_indexed),
            "fullRebuildExponent": scaling_exponent(rebuild_points),
            "deltaUpdateExponent": scaling_exponent(delta_points),
        },
        "acceptanceCriteria": {
            "contextAcceleration": "indexed contextual resolution median must be lower than naive whole-estate scan at the largest size",
            "definitionAcceleration": "indexed definition-chain traversal median must be lower than repeated whole-definition scan at the largest size",
            "incrementalAcceleration": "single semantic delta median must be lower than full estate rebuild median at the largest size",
            "translationIntegrity": "intent translation must emit TRANSLATED with one typed action/target scope",
            "scaling": "indexed/delta exponents should remain materially below their naive/rebuild counterparts as size grows",
        },
        "claimBoundary": [
            "This benchmark quantifies data-structure, traversal, definition-resolution, incremental-maintenance and translation effects only.",
            "It does not measure neural model inference quality or speed.",
            "It does not establish universal speedup for every query; selectivity, graph density and update rate materially affect results.",
            "Synthetic results must be repeated against the real Keddeh Systems estate and resident target host before market-performance claims are promoted.",
        ],
    }
    largest = results[-1]
    payload["observables"] = {
        "largestSize": largest["size"],
        "contextSpeedup": largest["contextResolution"]["speedup"],
        "definitionSpeedup": largest["definitionTraversal"]["speedup"],
        "incrementalSpeedup": largest["incrementalMaintenance"]["speedup"],
        "translationMedianNs": largest["intentTranslation"]["medianNs"],
    }
    payload["benchmarkHash"] = sha256_bytes(canonical_json_bytes(payload))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(OUT, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1000,5000,10000")
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    sizes = [int(x) for x in args.sizes.split(",") if int(x) > 0]
    if not sizes:
        raise SystemExit("at least one positive size required")
    result = bench(sizes, max(3, args.repeats))
    print(json.dumps(result, indent=2, sort_keys=True))
