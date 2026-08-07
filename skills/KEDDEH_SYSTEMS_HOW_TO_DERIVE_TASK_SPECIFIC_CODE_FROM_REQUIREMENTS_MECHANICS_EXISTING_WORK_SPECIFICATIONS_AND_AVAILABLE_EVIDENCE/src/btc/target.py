"""Mechanic: compact difficulty target (nBits) expansion and target verification."""

from __future__ import annotations


def bits_to_target(bits: int) -> int:
    """Expand the compact nBits encoding into a full 256-bit target integer."""
    if not 0 <= bits <= 0xFFFFFFFF:
        raise ValueError("bits must fit in 32 bits")
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    if bits & 0x00800000:
        # Negative sign bit set: not valid for a difficulty target.
        raise ValueError("negative target is invalid")
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    return target


def meets_target(block_hash_internal: bytes, bits: int) -> bool:
    """True when the block hash, read as a little-endian integer, is <= target."""
    if len(block_hash_internal) != 32:
        raise ValueError("block hash must be 32 bytes (internal order)")
    hash_value = int.from_bytes(block_hash_internal, "little")
    return hash_value <= bits_to_target(bits)
