#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from illlm_higher_order import begin_frame, build_topology, reenter_parent, route_to_role, traverse  # noqa: E402
from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes  # noqa: E402

OUT = BASE / "reports" / "kex-wbos" / "illlm-higher-order-benchmark.json"


def ns() -> int:
    return time.perf_counter_ns()


def bench(iterations: int = 2000) -> dict:
    cold_samples = []
    for _ in range(10):
        start = ns()
        topology = build_topology()
        cold_samples.append(ns() - start)

    topology = build_topology()
    sector_targets = route_to_role("SECTOR", topology)
    if not sector_targets:
        raise SystemExit("no sector IL-LLM targets discovered")

    role_samples = []
    traversal_samples = []
    reentry_samples = []
    for i in range(iterations):
        start = ns()
        targets = route_to_role("SECTOR", topology)
        role_samples.append(ns() - start)

        frame = begin_frame()
        start = ns()
        frame = traverse(frame, "il-llm://braink/sector", topology)
        frame = traverse(frame, targets[i % len(targets)], topology)
        traversal_samples.append(ns() - start)

        start = ns()
        frame = reenter_parent(frame)
        frame = reenter_parent(frame)
        reentry_samples.append(ns() - start)

    cold_median = statistics.median(cold_samples)
    role_median = statistics.median(role_samples)
    traversal_median = statistics.median(traversal_samples)
    reentry_median = statistics.median(reentry_samples)
    speedup = cold_median / max(1, traversal_median)

    result = {
        "schema": "kex.illlm.higher-order-benchmark.v1",
        "topologyHash": topology["topologyHash"],
        "nodes": topology["nodeCount"],
        "edges": topology["edgeCount"],
        "sectorTargets": len(sector_targets),
        "iterations": iterations,
        "nanoseconds": {
            "coldTopologyBuildMedian": cold_median,
            "warmRoleLookupMedian": role_median,
            "warmTwoLevelTraversalMedian": traversal_median,
            "warmTwoLevelReentryMedian": reentry_median,
        },
        "coldToWarmTraversalSpeedup": speedup,
        "claimBoundary": "This measures local topology construction versus already-indexed in-memory traversal. It is not an end-to-end LLM inference benchmark and does not establish production throughput until repeated on the resident target host.",
    }
    result["benchmarkHash"] = sha256_bytes(canonical_json_bytes(result))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(OUT, json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    result = bench()
    print(json.dumps(result, indent=2, sort_keys=True))
