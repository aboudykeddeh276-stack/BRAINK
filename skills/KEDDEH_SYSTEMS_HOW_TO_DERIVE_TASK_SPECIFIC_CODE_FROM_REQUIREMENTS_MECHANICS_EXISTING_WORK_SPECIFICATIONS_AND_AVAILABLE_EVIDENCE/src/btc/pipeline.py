"""The BTC assembly/execution chain — composed from the canonical mechanics.

This is the direct mechanical composition:

    template -> coinbase -> witness commitment -> merkle root -> header
             -> work -> hash -> candidate -> full block -> submit

It imports and CALLS the one authoritative implementation of each mechanic. It does
not re-implement any business logic. Tests, runtime, CLI, and packaging all consume
these same functions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .block import assemble_block
from .coinbase import TxOutput, build_coinbase_tx, coinbase_txid_internal
from .economics import coinbase_value
from .header import BlockHeader, block_hash_display, build_header
from .merkle import merkle_root
from .mining import reconstruct_candidate, search_nonce
from .stale import is_stale
from .submit import build_submitblock_request
from .template import BlockTemplate
from .witness import witness_commitment_script


@dataclass(frozen=True)
class PipelineResult:
    coinbase_txid_display: str
    merkle_root_internal: bytes
    winning_nonce: int | None
    block_hash_display: str | None
    block_bytes: bytes | None
    submit_request: dict | None
    stale: bool


def run_pipeline(
    template: BlockTemplate,
    payout_script: bytes,
    current_tip_internal: bytes | None = None,
    extranonce: bytes = b"",
    max_nonce_scan: int = 1 << 20,
    total_fees: int = 0,
) -> PipelineResult:
    """Run the full chain, passing each mechanic's output into the next.

    A regtest-style easy target is used so the demonstration terminates quickly;
    the mechanics themselves are consensus-correct regardless of difficulty.
    """
    # stale-work check comes first: never build on a superseded tip.
    tip = current_tip_internal if current_tip_internal is not None else template.prev_hash_internal
    stale = is_stale(template.prev_hash_internal, tip)
    if stale:
        return PipelineResult("", b"", None, None, None, None, True)

    # coinbase: value from economics, plus the BIP141 witness commitment output.
    non_coinbase_wtxids = [tx.wtxid_internal for tx in template.transactions]
    commitment_script = witness_commitment_script(non_coinbase_wtxids)
    outputs = [
        TxOutput(coinbase_value(template.height, total_fees), payout_script),
        TxOutput(0, commitment_script),
    ]
    coinbase_tx = build_coinbase_tx(template.height, outputs, extranonce=extranonce)
    coinbase_txid = coinbase_txid_internal(coinbase_tx)

    # merkle root over coinbase + template transactions.
    txids = [coinbase_txid] + [tx.txid_internal for tx in template.transactions]
    root = merkle_root(txids)

    # header prefix (76 bytes) = full header minus the 4-byte nonce.
    header_zero_nonce = build_header(
        BlockHeader(template.version, template.prev_hash_internal, root, template.curtime, template.bits, 0)
    )
    header_prefix = header_zero_nonce[:76]

    # hash / search for a satisfying nonce.
    winning_nonce = search_nonce(header_prefix, 0, max_nonce_scan, template.bits)
    if winning_nonce is None:
        return PipelineResult(root[::-1].hex(), root, None, None, None, None, False)

    # candidate reconstruction and full-block assembly.
    final_header = reconstruct_candidate(header_prefix, winning_nonce)
    other_txs = [tx.raw for tx in template.transactions if tx.raw]
    block_bytes = assemble_block(final_header, coinbase_tx, other_txs)

    # submit request (transport-free).
    submit_request = build_submitblock_request(block_bytes)

    return PipelineResult(
        coinbase_txid_display=coinbase_txid[::-1].hex(),
        merkle_root_internal=root,
        winning_nonce=winning_nonce,
        block_hash_display=block_hash_display(final_header),
        block_bytes=block_bytes,
        submit_request=submit_request,
        stale=False,
    )
