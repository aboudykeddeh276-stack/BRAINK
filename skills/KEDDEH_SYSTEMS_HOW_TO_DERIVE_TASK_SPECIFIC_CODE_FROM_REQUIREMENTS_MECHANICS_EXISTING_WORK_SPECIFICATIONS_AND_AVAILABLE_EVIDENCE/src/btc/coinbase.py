"""Mechanic: coinbase transaction construction (BIP34-compliant).

Produces the non-witness (legacy) serialization of the coinbase transaction,
which is what the txid commits to. The witness commitment output (BIP141) is
supplied by the witness mechanic and included as one of the outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bip34 import encode_bip34_height
from .serialize import compact_size, le_uint32, le_uint64, sha256d, var_bytes

_COINBASE_PREVOUT_HASH = b"\x00" * 32
_COINBASE_PREVOUT_INDEX = b"\xff\xff\xff\xff"
_SEQUENCE_FINAL = b"\xff\xff\xff\xff"


@dataclass(frozen=True)
class TxOutput:
    value: int          # satoshis
    script_pubkey: bytes


def build_coinbase_scriptsig(height: int, extranonce: bytes, tag: bytes = b"") -> bytes:
    """coinbase scriptSig = BIP34 height push || extranonce || optional tag."""
    return encode_bip34_height(height) + extranonce + tag


def build_coinbase_tx(
    height: int,
    outputs: list[TxOutput],
    extranonce: bytes = b"",
    tag: bytes = b"",
    version: int = 1,
    locktime: int = 0,
) -> bytes:
    """Serialize the non-witness coinbase transaction bytes."""
    if not outputs:
        raise ValueError("coinbase must have at least one output")
    scriptsig = build_coinbase_scriptsig(height, extranonce, tag)
    tx = bytearray()
    tx += le_uint32(version)
    tx += compact_size(1)                      # exactly one input
    tx += _COINBASE_PREVOUT_HASH
    tx += _COINBASE_PREVOUT_INDEX
    tx += var_bytes(scriptsig)
    tx += _SEQUENCE_FINAL
    tx += compact_size(len(outputs))
    for out in outputs:
        tx += le_uint64(out.value)
        tx += var_bytes(out.script_pubkey)
    tx += le_uint32(locktime)
    return bytes(tx)


def coinbase_txid_internal(coinbase_tx_bytes: bytes) -> bytes:
    """txid (internal order) of the non-witness coinbase serialization."""
    return sha256d(coinbase_tx_bytes)
