"""Mechanic: BIP141 segregated-witness commitment.

The witness commitment output script is:
    OP_RETURN (0x6a) <36-byte push 0x24> 0xaa21a9ed || witness_root_commitment

where witness_root_commitment = sha256d(witness_merkle_root || witness_reserved).
The coinbase's own wtxid is defined as 0x00..00 for the witness Merkle tree.
"""

from __future__ import annotations

from .merkle import merkle_root
from .serialize import sha256d

_WITNESS_HEADER = bytes.fromhex("6a24aa21a9ed")  # OP_RETURN, push 36, commitment tag
_COINBASE_WTXID = b"\x00" * 32


def witness_commitment_script(
    non_coinbase_wtxids_internal: list[bytes],
    witness_reserved_value: bytes = b"\x00" * 32,
) -> bytes:
    """Build the coinbase witness-commitment output scriptPubKey (BIP141)."""
    if len(witness_reserved_value) != 32:
        raise ValueError("witness_reserved_value must be 32 bytes")
    for wtxid in non_coinbase_wtxids_internal:
        if len(wtxid) != 32:
            raise ValueError("each wtxid must be 32 bytes (internal order)")
    wtxids = [_COINBASE_WTXID] + list(non_coinbase_wtxids_internal)
    witness_root = merkle_root(wtxids)
    commitment = sha256d(witness_root + witness_reserved_value)
    return _WITNESS_HEADER + commitment
