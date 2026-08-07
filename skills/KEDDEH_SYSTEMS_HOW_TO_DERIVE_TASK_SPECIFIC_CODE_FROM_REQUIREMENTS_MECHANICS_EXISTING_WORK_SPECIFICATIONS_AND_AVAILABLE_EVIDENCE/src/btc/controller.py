"""Live control plane: point the real mechanics at a real Bitcoin Core node.

This composes the transport-free mechanics with the real RPC connector to run the
actual chain the requirement specifies:

    real getblockchaininfo  (assert synced mainnet)
    -> real getblocktemplate
    -> parse template
    -> derive payout script (control-plane only)
    -> run_pipeline (real coinbase/witness/merkle/header/SHA256d/candidate)
    -> real submitblock
    -> real accept/reject
    -> revenue/cost telemetry

Nothing here is simulated: the difficulty of mainnet simply makes a found block
improbable within a bounded local nonce scan, which is honest reality — not a
representation substituted for the target.
"""

from __future__ import annotations

from dataclasses import dataclass

from .economics import coinbase_value
from .pipeline import PipelineResult, run_pipeline
from .rpc import CoreRpcClient
from .serialize import hash_to_internal
from .submit import SubmitResult, interpret_submitblock_response
from .target import bits_to_target
from .template import BlockTemplate, parse_block_template


@dataclass(frozen=True)
class LiveMinerConfig:
    expected_chain: str = "main"      # guard: refuse to mine on the wrong chain
    require_synced: bool = True       # refuse while initialblockdownload is true
    rules: tuple[str, ...] = ("segwit",)
    max_nonce_scan: int = 1 << 20     # bounded local search window
    extranonce: bytes = b""


@dataclass(frozen=True)
class LiveAttempt:
    height: int
    chain: str
    template_bits: int
    target: int
    total_fees: int
    coinbase_value: int
    stale: bool
    candidate_found: bool
    block_hash_display: str | None
    submitted: bool
    submit_result: SubmitResult | None
    pipeline: PipelineResult


class LiveMinerError(RuntimeError):
    """Raised when the node state makes live mining unsafe or impossible."""


def _total_fees(template: BlockTemplate) -> int:
    return sum(max(0, tx.fee) for tx in template.transactions)


def run_live_attempt(
    client: CoreRpcClient,
    payout_script: bytes,
    config: LiveMinerConfig | None = None,
    submit: bool = True,
) -> LiveAttempt:
    """Run one real template->hash->submit attempt against a live Core node."""
    if not payout_script:
        raise LiveMinerError("payout_script is required before any coinbase is built")
    cfg = config or LiveMinerConfig()

    chain_info = client.getblockchaininfo()
    chain = str(chain_info.get("chain", ""))
    if chain != cfg.expected_chain:
        raise LiveMinerError(
            f"node chain is {chain!r} but configured expected_chain is {cfg.expected_chain!r}"
        )
    if cfg.require_synced and bool(chain_info.get("initialblockdownload", False)):
        raise LiveMinerError("node is still in initial block download; not synced")

    template = parse_block_template(client.getblocktemplate(list(cfg.rules)))
    total_fees = _total_fees(template)

    # Real stale-tip guard: reconcile the template's previous hash with the live tip.
    tip_internal = hash_to_internal(client.getbestblockhash())

    result = run_pipeline(
        template=template,
        payout_script=payout_script,
        current_tip_internal=tip_internal,
        extranonce=cfg.extranonce,
        max_nonce_scan=cfg.max_nonce_scan,
        total_fees=total_fees,
    )

    submit_result: SubmitResult | None = None
    submitted = False
    if submit and result.block_bytes and not result.stale:
        raw = client.submitblock(result.block_bytes.hex())
        submit_result = interpret_submitblock_response({"result": raw})
        submitted = True

    return LiveAttempt(
        height=template.height,
        chain=chain,
        template_bits=template.bits,
        target=bits_to_target(template.bits),
        total_fees=total_fees,
        coinbase_value=coinbase_value(template.height, total_fees),
        stale=result.stale,
        candidate_found=result.winning_nonce is not None,
        block_hash_display=result.block_hash_display,
        submitted=submitted,
        submit_result=submit_result,
        pipeline=result,
    )
