"""Mechanic: block-template interpretation (getblocktemplate model)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .serialize import hash_to_internal


@dataclass(frozen=True)
class TemplateTransaction:
    txid_internal: bytes
    wtxid_internal: bytes
    raw: bytes
    fee: int


@dataclass(frozen=True)
class BlockTemplate:
    version: int
    prev_hash_internal: bytes
    bits: int
    curtime: int
    height: int
    transactions: list[TemplateTransaction] = field(default_factory=list)


def parse_block_template(gbt: dict) -> BlockTemplate:
    """Interpret a getblocktemplate result object into a BlockTemplate model."""
    for required in ("version", "previousblockhash", "bits", "curtime", "height"):
        if required not in gbt:
            raise ValueError(f"template is missing required field '{required}'")

    transactions: list[TemplateTransaction] = []
    for entry in gbt.get("transactions", []):
        raw = bytes.fromhex(entry["data"]) if "data" in entry else b""
        txid = hash_to_internal(entry["txid"]) if "txid" in entry else b""
        wtxid = hash_to_internal(entry["hash"]) if "hash" in entry else txid
        transactions.append(
            TemplateTransaction(
                txid_internal=txid,
                wtxid_internal=wtxid,
                raw=raw,
                fee=int(entry.get("fee", 0)),
            )
        )

    return BlockTemplate(
        version=int(gbt["version"]),
        prev_hash_internal=hash_to_internal(gbt["previousblockhash"]),
        bits=int(gbt["bits"], 16) if isinstance(gbt["bits"], str) else int(gbt["bits"]),
        curtime=int(gbt["curtime"]),
        height=int(gbt["height"]),
        transactions=transactions,
    )
