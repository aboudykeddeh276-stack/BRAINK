"""Mechanic: BIP34 coinbase-height scriptSig encoding.

BIP34 requires the coinbase scriptSig to begin with the block height, serialized
as a minimally-encoded, length-prefixed little-endian push.
"""

from __future__ import annotations


def encode_bip34_height(height: int) -> bytes:
    """Serialize a block height as a BIP34 minimally-encoded push (CScriptNum)."""
    if height < 0:
        raise ValueError("height must be non-negative")
    if height == 0:
        # A single zero byte push (OP_0 is not used here; BIP34 uses a push).
        return b"\x01\x00"
    magnitude = bytearray()
    n = height
    while n > 0:
        magnitude.append(n & 0xFF)
        n >>= 8
    # If the most-significant byte has its high bit set, append a 0x00 so the
    # value is not interpreted as negative (CScriptNum sign rule).
    if magnitude[-1] & 0x80:
        magnitude.append(0x00)
    return bytes([len(magnitude)]) + bytes(magnitude)
