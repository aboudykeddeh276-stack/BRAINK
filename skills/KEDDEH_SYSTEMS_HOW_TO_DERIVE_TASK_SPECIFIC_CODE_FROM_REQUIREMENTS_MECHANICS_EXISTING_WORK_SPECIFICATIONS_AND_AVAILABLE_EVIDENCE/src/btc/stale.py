"""Mechanic: stale-work detection.

Work issued against a previous-block hash that no longer matches the current chain
tip is stale and must be discarded before submission.
"""

from __future__ import annotations


def is_stale(work_prev_hash_internal: bytes, current_tip_internal: bytes) -> bool:
    """True when the work's previous-block hash no longer equals the current tip."""
    if len(work_prev_hash_internal) != 32 or len(current_tip_internal) != 32:
        raise ValueError("hashes must be 32 bytes (internal order)")
    return work_prev_hash_internal != current_tip_internal
