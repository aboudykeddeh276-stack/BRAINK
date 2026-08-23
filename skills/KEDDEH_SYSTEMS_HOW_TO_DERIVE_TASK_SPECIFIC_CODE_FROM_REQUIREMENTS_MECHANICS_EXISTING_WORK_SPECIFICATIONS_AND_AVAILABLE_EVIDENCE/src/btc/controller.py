"""Live control plane: point the real mechanics at a real Bitcoin Core node.

The control plane preserves Bitcoin authority while allowing the hashing workload to
be scheduled through multiple KEX worker lanes.
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
    expected_chain: str = "main"
    require_synced: bool = True
    rules: tuple[str, ...] = ("segwit",)
    max_nonce_scan: int = 1 << 20
    worker_count: int = 4
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
    """Run one real template -> concurrent hash -> submit attempt against Core."""
    if not payout_script:
        raise LiveMinerError("payout_script is required before any coinbase is built")
    cfg = config or LiveMinerConfig()
    if cfg.worker_count < 1:
        raise LiveMinerError("worker_count must be >= 1")

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
    tip_internal = hash_to_internal(client.getbestblockhash())

    result = run_pipeline(
        template=template,
        payout_script=payout_script,
        current_tip_internal=tip_internal,
        extranonce=cfg.extranonce,
        max_nonce_scan=cfg.max_nonce_scan,
        total_fees=total_fees,
        worker_count=cfg.worker_count,
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
