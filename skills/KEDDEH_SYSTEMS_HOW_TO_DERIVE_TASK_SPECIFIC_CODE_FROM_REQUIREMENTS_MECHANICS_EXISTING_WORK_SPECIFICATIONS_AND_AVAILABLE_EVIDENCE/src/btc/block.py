"""Mechanic: full block serialization.

Serializes a block in legacy (non-witness) form: the 80-byte header, a CompactSize
transaction count, then each raw transaction in order. The coinbase must be first.

Boundary: witness (segwit) serialization with the marker/flag and witness stacks is
out of scope for this mechanic; the coinbase commits to the witness data via the
BIP141 commitment output produced by `witness.py`, and txids/wtxids drive the Merkle
mechanics. This keeps one authoritative assembly path for the demonstrated chain.
"""

from __future__ import annotations

from .serialize import compact_size


def assemble_block(header_bytes: bytes, coinbase_tx: bytes, other_txs: list[bytes]) -> bytes:
    """Concatenate header + tx count + coinbase + remaining transactions."""
    if len(header_bytes) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if not coinbase_tx:
        raise ValueError("coinbase transaction bytes are required")
    txs = [coinbase_tx] + list(other_txs)
    block = bytearray()
    block += header_bytes
    block += compact_size(len(txs))
    for tx in txs:
        block += tx
    return bytes(block)
