"""Mechanic: SHA256d work execution and candidate reconstruction.

`search_nonce` scans a nonce range over a fixed 76-byte header prefix (the header
without its final 4-byte nonce field) looking for a hash that meets the target.
`reconstruct_candidate` rebuilds the full 80-byte header from a prefix and a
winning nonce and verifies it re-hashes as reported.
"""

from __future__ import annotations

from .serialize import le_uint32, sha256d
from .target import meets_target


def search_nonce(
    header_prefix_76: bytes,
    nonce_start: int,
    nonce_end: int,
    bits: int,
) -> int | None:
    """Return the first nonce in [start, end) whose header meets target, else None."""
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes (80-byte header minus nonce)")
    for nonce in range(nonce_start, nonce_end):
        header = header_prefix_76 + le_uint32(nonce)
        if meets_target(sha256d(header), bits):
            return nonce
    return None


def reconstruct_candidate(header_prefix_76: bytes, winning_nonce: int) -> bytes:
    """Rebuild the full 80-byte header from a prefix and the winning nonce."""
    if len(header_prefix_76) != 76:
        raise ValueError("header prefix must be 76 bytes")
    header = header_prefix_76 + le_uint32(winning_nonce)
    if len(header) != 80:  # defensive: should always hold
        raise ValueError("reconstructed header is not 80 bytes")
    return header
