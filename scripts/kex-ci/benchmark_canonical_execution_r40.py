from __future__ import annotations

import json
import os
import platform
import resource
import statistics
import tempfile
import time
from pathlib import Path

from deployment.kex_runtime_service_r40 import CanonicalRuntimeHost


def state_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file()) if root.exists() else 0


def command(value: int):
    return {
        "source": f"benchmark://r40/{value}",
        "data_class": "CORRECTION",
        "payload": {"sequence": value},
        "authority": "authority://source/local",
        "capabilities": ["process", "readback"],
        "illlm": {"intent": "state.write", "lineage": "A", "key": "benchmark_value", "value": value},
    }


def percentile(values, p):
    values = sorted(values)
    if not values: return None
    index = min(len(values) - 1, max(0, round((p / 100) * (len(values) - 1))))
    return values[index]


def main():
    samples = []
    errors = 0
    with tempfile.TemporaryDirectory(prefix="braink-r40-bench-") as tmp:
        state = Path(tmp) / "state"
        before = state_bytes(state)
        cpu_before = time.process_time()
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        cold_start = time.perf_counter_ns()
        host = CanonicalRuntimeHost(state, "A")
        cold_result = host.canonical_execute(command(0))
        cold_ms = (time.perf_counter_ns() - cold_start) / 1_000_000
        if str(cold_result.get("status", "")).startswith(("BLOCKED:", "FAILED:")): errors += 1

        for value in range(1, 21):
            started = time.perf_counter_ns()
            result = host.canonical_execute(command(value))
            samples.append((time.perf_counter_ns() - started) / 1_000_000)
            if str(result.get("status", "")).startswith(("BLOCKED:", "FAILED:")): errors += 1

        cpu_after = time.process_time()
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        after = state_bytes(state)
        report = {
            "schema": "braink.canonical-benchmark.r40/v1",
            "operation": "canonical correction",
            "workload": {"cold_operations": 1, "warm_operations": len(samples)},
            "dataset_state_size_bytes": after,
            "host": {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()},
            "runtime": "KEDDEH-KEX-R40",
            "cold_ms": cold_ms,
            "warm": {"median_ms": statistics.median(samples), "p95_ms": percentile(samples, 95), "p99_ms": percentile(samples, 99)},
            "memory": {"ru_maxrss_before": rss_before, "ru_maxrss_after": rss_after, "unit": "platform-native ru_maxrss"},
            "cpu_seconds": cpu_after - cpu_before,
            "io": {"state_bytes_before": before, "state_bytes_after": after, "state_bytes_delta": after - before},
            "error_rate": errors / (len(samples) + 1),
            "performance_gate": None,
        }
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
