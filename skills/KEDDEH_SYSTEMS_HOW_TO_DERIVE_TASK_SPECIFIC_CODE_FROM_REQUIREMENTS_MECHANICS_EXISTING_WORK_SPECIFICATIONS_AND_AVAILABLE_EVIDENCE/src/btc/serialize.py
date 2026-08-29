"""Serialization primitives shared by every BTC mechanic.

These are the low-level byte transformations (Bitcoin uses little-endian
serialization with CompactSize prefixes). They are implemented once here and
consumed by every other mechanic module.
"""

from __future__ import annotations

import hashlib


def sha256d(data: bytes) -> bytes:
    """Bitcoin double SHA-256: SHA256(SHA256(data)), 32 bytes, internal order."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def le_uint32(value: int) -> bytes:
    """Serialize an unsigned 32-bit integer, little-endian."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"value {value} out of range for uint32")
    return value.to_bytes(4, "little")


def le_int32(value: int) -> bytes:
    """Serialize a signed 32-bit integer, little-endian (block version field)."""
    return value.to_bytes(4, "little", signed=True)


def le_uint64(value: int) -> bytes:
    """Serialize an unsigned 64-bit integer, little-endian (output amount, satoshis)."""
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"value {value} out of range for uint64")
    return value.to_bytes(8, "little")


def compact_size(n: int) -> bytes:
    """Serialize a CompactSize (Bitcoin varint) unsigned integer."""
    if n < 0:
        raise ValueError("compact_size requires a non-negative integer")
    if n < 0xFD:
        return n.to_bytes(1, "little")
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    return b"\xff" + n.to_bytes(8, "little")


def var_bytes(data: bytes) -> bytes:
    """A CompactSize length prefix followed by the raw bytes."""
    return compact_size(len(data)) + data


def hash_to_internal(display_hex: str) -> bytes:
    """Convert a display (big-endian hex) hash to internal (little-endian) bytes."""
    raw = bytes.fromhex(display_hex)
    if len(raw) != 32:
        raise ValueError("a Bitcoin hash must be 32 bytes")
    return raw[::-1]


def internal_to_display(internal: bytes) -> str:
    """Convert internal (little-endian) hash bytes to display (big-endian) hex."""
    if len(internal) != 32:
        raise ValueError("a Bitcoin hash must be 32 bytes")
    return internal[::-1].hex()
