"""Mechanic: SHA256d work execution and candidate reconstruction.

`search_nonce` scans one nonce range. `search_nonce_concurrent` executes multiple
non-overlapping lane ranges concurrently against the same Bitcoin SHA256d/target
predicate. Concurrency changes scheduling only; it does not redefine validity.

Both search paths accept an optional external stop event.  That event is the
lifecycle cancellation edge used by BRAINK/Core tip monitoring: a newly observed
chain tip can stop active hashing without waiting for the nonce window to finish.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event

from .serialize import le_uint32, sha256d
from .target import meets_target
from .work import WorkRange, allocate_work_window


def search_nonce(
    header_prefix_76: bytes,
    nonce_start: int,
    nonce_end: int,
    bits: int,
    stop_event: Event | None = None,
) -> int | None:
    """Return the first nonce in [start, end) whose header meets target.

    When ``stop_event`` is set the search terminates cooperatively and returns
    ``None``.  The caller decides whether that cancellation means stale work,
    explicit shutdown, or another lifecycle transition.
    """
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes (80-byte header minus nonce)")
    for nonce in range(nonce_start, nonce_end):
        if stop_event is not None and stop_event.is_set():
            return None
        header = header_prefix_76 + le_uint32(nonce)
        if meets_target(sha256d(header), bits):
            return nonce
    return None


def _search_lane(
    header_prefix_76: bytes,
    work: WorkRange,
    bits: int,
    stop: Event,
) -> int | None:
    for nonce in range(work.nonce_start, work.nonce_end):
        if stop.is_set():
            return None
        header = header_prefix_76 + le_uint32(nonce)
        if meets_target(sha256d(header), bits):
            stop.set()
            return nonce
    return None


def search_nonce_concurrent(
    header_prefix_76: bytes,
    nonce_start: int,
    nonce_end: int,
    bits: int,
    worker_count: int,
    stop_event: Event | None = None,
) -> int | None:
    """Search disjoint nonce lanes concurrently and stop peers cooperatively.

    Every lane evaluates exactly the same Bitcoin predicate as `search_nonce`.
    ``stop_event`` may be supplied by the live lifecycle so stale-tip detection or
    explicit shutdown can cancel all lanes while hashing is active.
    """
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes (80-byte header minus nonce)")
    ranges = allocate_work_window(nonce_start, nonce_end, worker_count)
    if not ranges:
        return None

    stop = stop_event if stop_event is not None else Event()
    if stop.is_set():
        return None
    if len(ranges) == 1:
        return search_nonce(
            header_prefix_76,
            ranges[0].nonce_start,
            ranges[0].nonce_end,
            bits,
            stop_event=stop,
        )

    executor = ThreadPoolExecutor(max_workers=len(ranges), thread_name_prefix="kex-btc-lane")
    futures = [executor.submit(_search_lane, header_prefix_76, work, bits, stop) for work in ranges]
    try:
        for future in as_completed(futures):
            nonce = future.result()
            if nonce is not None:
                stop.set()
                for pending in futures:
                    pending.cancel()
                return nonce
        return None
    finally:
        stop.set()
        executor.shutdown(wait=True, cancel_futures=True)


def reconstruct_candidate(header_prefix_76: bytes, winning_nonce: int) -> bytes:
    """Rebuild the full 80-byte header from a prefix and the winning nonce."""
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes")
    header = header_prefix_76 + le_uint32(winning_nonce)
    if len(header) != 80:
        raise ValueError("reconstructed header is not 80 bytes")
    return header
