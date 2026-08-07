"""Mechanic: work-space allocation across the mining workload.

Partitions the 32-bit nonce space into disjoint, bounded ranges, one per worker.
"""

from __future__ import annotations

from dataclasses import dataclass

_NONCE_SPACE = 1 << 32  # 2**32 distinct nonces


@dataclass(frozen=True)
class WorkRange:
    worker_index: int
    nonce_start: int
    nonce_end: int  # exclusive


def allocate_work(worker_count: int) -> list[WorkRange]:
    """Split the full nonce space into `worker_count` disjoint ranges."""
    if worker_count < 1:
        raise ValueError("worker_count must be >= 1")
    if worker_count > _NONCE_SPACE:
        raise ValueError("worker_count exceeds the nonce space")
    base, remainder = divmod(_NONCE_SPACE, worker_count)
    ranges: list[WorkRange] = []
    start = 0
    for i in range(worker_count):
        size = base + (1 if i < remainder else 0)
        ranges.append(WorkRange(i, start, start + size))
        start += size
    return ranges
