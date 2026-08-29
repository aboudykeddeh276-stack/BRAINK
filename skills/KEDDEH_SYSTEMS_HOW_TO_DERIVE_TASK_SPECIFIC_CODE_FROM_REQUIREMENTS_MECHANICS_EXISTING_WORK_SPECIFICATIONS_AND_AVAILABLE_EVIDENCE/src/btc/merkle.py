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


def coinbase_merkle_branch(non_coinbase_txids_internal: list[bytes]) -> list[bytes]:
    """Merkle branch (sibling path) for the coinbase at leaf index 0.

    This is exactly the ``merkle_branch`` a Stratum server sends in ``mining.notify``:
    the ordered list of sibling hashes needed to fold a miner-reconstructed coinbase
    txid up to the Merkle root. The coinbase itself is not yet known to the branch,
    so leaf 0 is a placeholder and only the non-coinbase txids drive the siblings.
    """
    for txid in non_coinbase_txids_internal:
        if len(txid) != 32:
            raise ValueError("each txid must be 32 bytes (internal order)")
    branch: list[bytes] = []
    # Leaf 0 is the (not-yet-known) coinbase; use a placeholder that never affects
    # the recorded siblings.
    layer = [b"\x00" * 32] + list(non_coinbase_txids_internal)
    index = 0
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        sibling = index ^ 1
        branch.append(layer[sibling])
        layer = [sha256d(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        index //= 2
    return branch


def apply_coinbase_branch(coinbase_txid_internal: bytes, branch: list[bytes]) -> bytes:
    """Fold a coinbase txid up through a Stratum Merkle branch to the root."""
    if len(coinbase_txid_internal) != 32:
        raise ValueError("coinbase txid must be 32 bytes (internal order)")
    acc = coinbase_txid_internal
    for sibling in branch:
        if len(sibling) != 32:
            raise ValueError("each branch element must be 32 bytes")
        acc = sha256d(acc + sibling)
    return acc
