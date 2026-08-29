"""Mechanic: work-space allocation across the mining workload.

The same Bitcoin nonce space can be divided into disjoint worker/lane ranges.  This
changes execution geometry only; it does not change the Bitcoin validity predicate.
"""

from __future__ import annotations

from dataclasses import dataclass

_NONCE_SPACE = 1 << 32


@dataclass(frozen=True)
class WorkRange:
    worker_index: int
    nonce_start: int
    nonce_end: int  # exclusive


def allocate_work_window(nonce_start: int, nonce_end: int, worker_count: int) -> list[WorkRange]:
    """Split [nonce_start, nonce_end) into disjoint, contiguous worker ranges."""
    if worker_count < 1:
        raise ValueError("worker_count must be >= 1")
    if nonce_start < 0 or nonce_end < 0 or nonce_start > nonce_end:
        raise ValueError("invalid nonce window")
    if nonce_end > _NONCE_SPACE:
        raise ValueError("nonce window exceeds the 32-bit nonce space")
    width = nonce_end - nonce_start
    if width == 0:
        return []
    active_workers = min(worker_count, width)
    base, remainder = divmod(width, active_workers)
    ranges: list[WorkRange] = []
    start = nonce_start
    for i in range(active_workers):
        size = base + (1 if i < remainder else 0)
        ranges.append(WorkRange(i, start, start + size))
        start += size
    return ranges


def allocate_work(worker_count: int) -> list[WorkRange]:
    """Split the full 32-bit nonce space into disjoint worker ranges."""
    if worker_count > _NONCE_SPACE:
        raise ValueError("worker_count exceeds the nonce space")
    return allocate_work_window(0, _NONCE_SPACE, worker_count)
