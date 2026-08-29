"""Mechanic: measure the actual execution rate and economics of the miner.

Capability is the centre: a benchmark exists because it tells us where to improve.
This module executes the *real* SHA256d search work over a bounded window and
reports the measured rate, so optimisation decisions are driven by observed
behaviour rather than assertion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .economics import COIN, coinbase_value
from .serialize import le_uint32, sha256d


@dataclass(frozen=True)
class HashRateMeasurement:
    hashes: int
    elapsed_seconds: float
    hashes_per_second: float


def measure_hashrate_by_count(header_prefix_76: bytes, iterations: int) -> HashRateMeasurement:
    """Execute exactly `iterations` real SHA256d hashes and measure the rate.

    Deterministic in the amount of work performed (good for tests and CI), while
    still exercising the identical hashing path used by the miner.
    """
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    start = time.perf_counter()
    for nonce in range(iterations):
        sha256d(header_prefix_76 + le_uint32(nonce))
    elapsed = time.perf_counter() - start
    rate = iterations / elapsed if elapsed > 0 else float("inf")
    return HashRateMeasurement(iterations, elapsed, rate)


def measure_hashrate_by_time(header_prefix_76: bytes, seconds: float) -> HashRateMeasurement:
    """Execute real SHA256d hashes for ~`seconds` and measure the achieved rate."""
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes")
    if seconds <= 0:
        raise ValueError("seconds must be > 0")
    start = time.perf_counter()
    hashes = 0
    nonce = 0
    while True:
        sha256d(header_prefix_76 + le_uint32(nonce & 0xFFFFFFFF))
        hashes += 1
        nonce += 1
        if (hashes & 0x3FFF) == 0 and (time.perf_counter() - start) >= seconds:
            break
    elapsed = time.perf_counter() - start
    rate = hashes / elapsed if elapsed > 0 else float("inf")
    return HashRateMeasurement(hashes, elapsed, rate)


def expected_value_per_block_btc(height: int, total_fees: int) -> float:
    """The coinbase value at a height, expressed in BTC (economics measurement)."""
    return coinbase_value(height, total_fees) / COIN


def expected_reward_rate_btc_per_hour(
    height: int,
    total_fees: int,
    blocks_found_per_hour: float,
) -> float:
    """Projected reward in BTC/hour given an observed block-discovery rate."""
    if blocks_found_per_hour < 0:
        raise ValueError("blocks_found_per_hour must be non-negative")
    return expected_value_per_block_btc(height, total_fees) * blocks_found_per_hour
