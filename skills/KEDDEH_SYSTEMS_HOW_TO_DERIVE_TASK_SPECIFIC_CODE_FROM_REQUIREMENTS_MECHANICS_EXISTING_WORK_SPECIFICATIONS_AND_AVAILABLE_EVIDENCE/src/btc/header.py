"""Mechanic: 80-byte block header construction and block hashing."""

from __future__ import annotations

from dataclasses import dataclass

from .serialize import internal_to_display, le_int32, le_uint32, sha256d


@dataclass(frozen=True)
class BlockHeader:
    version: int
    prev_hash_internal: bytes   # 32 bytes, internal (little-endian) order
    merkle_root_internal: bytes  # 32 bytes, internal (little-endian) order
    time: int
    bits: int
    nonce: int

    def __post_init__(self) -> None:
        if len(self.prev_hash_internal) != 32:
            raise ValueError("prev_hash_internal must be 32 bytes")
        if len(self.merkle_root_internal) != 32:
            raise ValueError("merkle_root_internal must be 32 bytes")


def build_header(header: BlockHeader) -> bytes:
    """Serialize the canonical 80-byte block header (all little-endian)."""
    serialized = (
        le_int32(header.version)
        + header.prev_hash_internal
        + header.merkle_root_internal
        + le_uint32(header.time)
        + le_uint32(header.bits)
        + le_uint32(header.nonce)
    )
    if len(serialized) != 80:
        raise ValueError(f"header serialized to {len(serialized)} bytes, expected 80")
    return serialized


def block_hash_internal(header_bytes: bytes) -> bytes:
    """sha256d of the 80-byte header, internal (little-endian) order."""
    if len(header_bytes) != 80:
        raise ValueError("header must be exactly 80 bytes")
    return sha256d(header_bytes)


def block_hash_display(header_bytes: bytes) -> str:
    """The block hash in conventional display form (big-endian hex)."""
    return internal_to_display(block_hash_internal(header_bytes))
