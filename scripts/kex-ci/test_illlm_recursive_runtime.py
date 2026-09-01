#!/usr/bin/env python3
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from illlm_recursive_runtime import ILLLMNode, RecursiveILLLMRuntime, TraversalEdge, seed_primitive_ladder, _tokens


def build_runtime(sectors: int = 80, specialists_per_sector: int = 12) -> RecursiveILLLMRuntime:
    runtime = RecursiveILLLMRuntime()
    seed_primitive_ladder(runtime)
    sector_parent = "il-llm://foundation/sector"
    runtime_parent = "il-llm://foundation/runtime"
    for sector in range(sectors):
        sid = f"il-llm://braink/sector/s{sector:03d}"
        runtime.register_node(ILLLMNode(
            identity=sid,
            role="SECTOR",
            parent=sector_parent,
            semantic_terms=_tokens([f"sector-{sector}", "professional", "domain", "service"]),
            mathematical_state={"sector": sector},
            observed_state="RESIDENT",
        ))
        for specialist in range(specialists_per_sector):
            nid = f"{sid}/specialist/{specialist:02d}"
            terms = [
                f"sector-{sector}", f"specialist-{specialist}", "contextual", "machine", "executable",
                "evidence" if specialist % 3 == 0 else "service",
            ]
            runtime.register_node(ILLLMNode(
                identity=nid,
                role="SPECIALIST",
                parent=sid,
                semantic_terms=_tokens(terms),
                mathematical_state={"sector": sector, "specialist": specialist},
                execution_routes=(f"kex://execute/sector/{sector}/{specialist}",),
                observed_state="RESIDENT",
            ))
            runtime.add_edge(TraversalEdge(
                nid,
                runtime_parent,
                "EXECUTE_IN_RUNTIME",
                cost=0.5,
                executable=True,
                execution_route=f"kex://execute/sector/{sector}/{specialist}",
            ))
            runtime.add_edge(TraversalEdge(runtime_parent, nid, "READBACK_TO_CONTEXT", cost=0.5))
    return runtime


def cold_scan(runtime: RecursiveILLLMRuntime, query: str) -> list[str]:
    q = _tokens([query])
    scored = []
    for identity, node in runtime.nodes.items():
        overlap = len(q & node.semantic_terms)
        if overlap:
            scored.append((-overlap, identity))
    scored.sort()
    return [identity for _, identity in scored[:8]]


def benchmark(runtime: RecursiveILLLMRuntime, query: str, loops: int = 600) -> dict:
    cold_samples = []
    warm_samples = []
    for _ in range(7):
        start = time.perf_counter_ns()
        for _ in range(loops):
            cold_scan(runtime, query)
        cold_samples.append(time.perf_counter_ns() - start)

        start = time.perf_counter_ns()
        for _ in range(loops):
            runtime.contextual_candidates(query, role="SPECIALIST", require_execution=True, limit=8)
        warm_samples.append(time.perf_counter_ns() - start)

    cold = statistics.median(cold_samples)
    warm = statistics.median(warm_samples)
    return {
        "nodes": len(runtime.nodes),
        "loops": loops,
        "coldMedianNs": cold,
        "warmMedianNs": warm,
        "routingSpeedup": cold / warm if warm else None,
        "claimBoundary": "This ratio measures Python in-memory candidate routing on this synthetic topology only. It is not LLM inference, storage, network, end-to-end application, or production throughput speedup.",
    }


def main() -> None:
    runtime = build_runtime()

    assert runtime.snapshot()["nodeCount"] > 900
    assert runtime.snapshot()["semantics"]["containment"] == "ACYCLIC_ANCESTRY"
    assert runtime.snapshot()["semantics"]["traversal"] == "CYCLIC_ALLOWED"

    target = "il-llm://braink/sector/s042/specialist/03"
    frame = runtime.enter(target, query="sector-42 specialist-3 evidence executable")
    assert frame.current == target
    assert frame.ancestry[-1] == target
    parent = runtime.reenter_parent(frame.frame_id)
    assert parent.current == "il-llm://braink/sector/s042"

    candidates = runtime.contextual_candidates(
        "sector-42 specialist-3 evidence executable",
        role="SPECIALIST",
        require_execution=True,
    )
    assert candidates and candidates[0]["identity"] == target

    path = runtime.shortest_traversal(target, "il-llm://foundation/runtime")
    assert path["found"] is True
    assert path["executionRoutes"] == ["kex://execute/sector/42/3"]

    plan = runtime.compile_context_plan(
        "sector-42 specialist-3 evidence executable",
        role="SPECIALIST",
        require_execution=True,
    )
    assert plan["selected"]["identity"] == target
    assert plan["planHash"]

    # Traversal cycles are legal and should not corrupt containment ancestry.
    runtime.add_edge(TraversalEdge("il-llm://foundation/runtime", target, "REENTER_CONTEXT", cost=0.25))
    cycle_path = runtime.shortest_traversal("il-llm://foundation/runtime", target)
    assert cycle_path["found"] is True
    assert runtime.ancestry(target)[-1] == target

    # Containment cycles are forbidden.
    try:
        runtime.register_node(ILLLMNode(
            identity="il-llm://meta/il-llm-of-il-llms",
            role="META_RUNTIME",
            parent=target,
        ))
        raise AssertionError("containment cycle was accepted")
    except ValueError:
        pass

    result = benchmark(runtime, "sector-42 specialist-3 evidence executable")
    assert result["routingSpeedup"] is not None
    # No arbitrary performance threshold: noisy CI/hosts should not turn an
    # optimization measurement into a correctness failure.
    print(result)
    print("ILLLM_RECURSIVE_RUNTIME_PASS")


if __name__ == "__main__":
    main()
