#!/usr/bin/env python3
from __future__ import annotations

import math
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ExperimentSample:
    order: str
    a_ns: int
    b_ns: int


def _timed(fn: Callable[[], Any]) -> int:
    start = time.perf_counter_ns()
    fn()
    return time.perf_counter_ns() - start


def _mean_ci95(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    mean = statistics.fmean(values)
    if len(values) < 2:
        return (mean, mean)
    sd = statistics.stdev(values)
    half = 1.96 * sd / math.sqrt(len(values))
    return (mean - half, mean + half)


def _lag1(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    mean = statistics.fmean(values)
    denom = sum((x - mean) ** 2 for x in values)
    if denom == 0:
        return 0.0
    return sum((values[i] - mean) * (values[i - 1] - mean) for i in range(1, len(values))) / denom


def run_counterbalanced(
    a: Callable[[], Any],
    b: Callable[[], Any],
    *,
    trials: int = 30,
    seed: int = 297,
    warmups: int = 3,
) -> dict[str, Any]:
    if trials < 4:
        raise ValueError("at least four trials required")
    for _ in range(max(0, warmups)):
        a(); b()

    rng = random.Random(seed)
    orders = ["AB" if i % 2 == 0 else "BA" for i in range(trials)]
    rng.shuffle(orders)
    samples: list[ExperimentSample] = []

    for order in orders:
        if order == "AB":
            a_ns = _timed(a)
            b_ns = _timed(b)
        else:
            b_ns = _timed(b)
            a_ns = _timed(a)
        samples.append(ExperimentSample(order, a_ns, b_ns))

    a_values = [s.a_ns for s in samples]
    b_values = [s.b_ns for s in samples]
    ratios = [a / max(1, b) for a, b in zip(a_values, b_values)]
    a_ci = _mean_ci95([float(x) for x in a_values])
    b_ci = _mean_ci95([float(x) for x in b_values])

    return {
        "schema": "kex.experiment.counterbalanced.v1",
        "trials": trials,
        "warmups": warmups,
        "seed": seed,
        "rawSamples": [s.__dict__ for s in samples],
        "A": {
            "meanNs": statistics.fmean(a_values),
            "medianNs": statistics.median(a_values),
            "p95Ns": sorted(a_values)[min(len(a_values) - 1, math.ceil(len(a_values) * 0.95) - 1)],
            "stdevNs": statistics.stdev(a_values) if len(a_values) > 1 else 0.0,
            "meanCI95Ns": list(a_ci),
            "lag1Autocorrelation": _lag1([float(x) for x in a_values]),
        },
        "B": {
            "meanNs": statistics.fmean(b_values),
            "medianNs": statistics.median(b_values),
            "p95Ns": sorted(b_values)[min(len(b_values) - 1, math.ceil(len(b_values) * 0.95) - 1)],
            "stdevNs": statistics.stdev(b_values) if len(b_values) > 1 else 0.0,
            "meanCI95Ns": list(b_ci),
            "lag1Autocorrelation": _lag1([float(x) for x in b_values]),
        },
        "comparison": {
            "medianRatioAOverB": statistics.median(ratios),
            "meanRatioAOverB": statistics.fmean(ratios),
            "ABTrials": sum(1 for x in orders if x == "AB"),
            "BATrials": sum(1 for x in orders if x == "BA"),
        },
        "claimBoundary": [
            "Counterbalancing reduces order bias but does not prove independence.",
            "Lag-1 autocorrelation is a diagnostic, not a complete stationarity test.",
            "Resident-system claims require separate process-generation and destructive recovery experiments.",
        ],
    }
