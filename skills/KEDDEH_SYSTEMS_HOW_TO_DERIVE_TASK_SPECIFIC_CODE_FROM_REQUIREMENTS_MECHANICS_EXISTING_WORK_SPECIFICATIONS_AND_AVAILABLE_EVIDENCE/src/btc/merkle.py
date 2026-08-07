"""Mechanic: transaction Merkle root construction.

Bitcoin Merkle rule: hash pairs of txids with sha256d; when a row has an odd
number of nodes, the last node is duplicated. Inputs are internal-order 32-byte
hashes; the returned root is internal order.
"""

from __future__ import annotations

from .serialize import sha256d


def merkle_root(txids_internal: list[bytes]) -> bytes:
    """Compute the Merkle root over an ordered list of internal-order txids."""
    if not txids_internal:
        raise ValueError("cannot compute a Merkle root over an empty transaction set")
    for txid in txids_internal:
        if len(txid) != 32:
            raise ValueError("each txid must be 32 bytes (internal order)")

    layer = list(txids_internal)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])  # duplicate the last node on odd rows
        layer = [sha256d(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]
