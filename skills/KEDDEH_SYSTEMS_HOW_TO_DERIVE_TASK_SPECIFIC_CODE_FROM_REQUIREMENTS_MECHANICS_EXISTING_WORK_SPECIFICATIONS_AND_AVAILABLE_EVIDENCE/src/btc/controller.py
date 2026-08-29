"""Live control plane: bind canonical BTC mechanics to a real Bitcoin Core node.

The control plane preserves Bitcoin authority while allowing the hashing workload to
be scheduled through multiple KEX worker lanes.  The continuous lifecycle keeps the
objective active: refresh Core state, obtain work, hash, cancel stale work, roll the
work space, submit candidates, reconcile the result, and continue until explicitly
stopped or a fatal invariant is violated.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from typing import Callable

from .economics import coinbase_value
from .pipeline import PipelineResult, run_pipeline
from .rpc import CoreRpcClient, RpcError
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
    stale_poll_seconds: float = 1.0
    retry_initial_seconds: float = 1.0
    retry_max_seconds: float = 30.0


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


@dataclass(frozen=True)
class LifecycleSummary:
    rounds: int
    templates: int
    stale_cancellations: int
    nonce_exhaustions: int
    candidates: int
    submissions: int
    accepted: int
    rejected: int
    transient_errors: int
    stopped: bool
    last_height: int | None
    last_block_hash_display: str | None


class LiveMinerError(RuntimeError):
    """Raised when node/config state makes live mining unsafe or impossible."""


def _total_fees(template: BlockTemplate) -> int:
    return sum(max(0, tx.fee) for tx in template.transactions)


def _validate_config(cfg: LiveMinerConfig) -> None:
    if cfg.worker_count < 1:
        raise LiveMinerError("worker_count must be >= 1")
    if cfg.max_nonce_scan < 0 or cfg.max_nonce_scan > (1 << 32):
        raise LiveMinerError("max_nonce_scan must fit the 32-bit nonce space")
    if cfg.stale_poll_seconds <= 0:
        raise LiveMinerError("stale_poll_seconds must be > 0")
    if cfg.retry_initial_seconds < 0 or cfg.retry_max_seconds < cfg.retry_initial_seconds:
        raise LiveMinerError("retry interval configuration is invalid")


def _validate_chain(chain_info: dict, cfg: LiveMinerConfig) -> str:
    chain = str(chain_info.get("chain", ""))
    if chain != cfg.expected_chain:
        raise LiveMinerError(
            f"node chain is {chain!r} but configured expected_chain is {cfg.expected_chain!r}"
        )
    if cfg.require_synced and bool(chain_info.get("initialblockdownload", False)):
        raise LiveMinerError("node is still in initial block download; not synced")
    return chain


def _round_extranonce(base: bytes, counter: int) -> bytes:
    """Create a deterministic work-space rollover without changing Bitcoin validity."""
    if counter < 0:
        raise ValueError("extranonce counter cannot be negative")
    return base + counter.to_bytes(8, "little", signed=False)


def _watch_tip(
    client: CoreRpcClient,
    expected_prev_hash_internal: bytes,
    round_stop: Event,
    lifecycle_stop: Event,
    poll_seconds: float,
    state: dict[str, str],
) -> None:
    """Cancel an active hash round as soon as Core exposes a different best tip."""
    while not round_stop.wait(poll_seconds):
        if lifecycle_stop.is_set():
            state["reason"] = "explicit_stop"
            round_stop.set()
            return
        try:
            current_tip = hash_to_internal(client.getbestblockhash())
        except (RpcError, OSError) as exc:
            state["last_observation_error"] = str(exc)
            continue
        if current_tip != expected_prev_hash_internal:
            state["reason"] = "stale_tip"
            round_stop.set()
            return


def run_live_attempt(
    client: CoreRpcClient,
    payout_script: bytes,
    config: LiveMinerConfig | None = None,
    submit: bool = True,
) -> LiveAttempt:
    """Run one real template -> concurrent hash -> submit attempt against Core.

    This remains as the bounded diagnostic primitive.  Normal lifecycle execution is
    ``run_continuous_miner`` below.
    """
    if not payout_script:
        raise LiveMinerError("payout_script is required before any coinbase is built")
    cfg = config or LiveMinerConfig()
    _validate_config(cfg)

    chain_info = client.getblockchaininfo()
    chain = _validate_chain(chain_info, cfg)

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


def run_continuous_miner(
    client: CoreRpcClient,
    payout_script: bytes,
    config: LiveMinerConfig | None = None,
    submit: bool = True,
    stop_event: Event | None = None,
    max_rounds: int | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> LifecycleSummary:
    """Keep the BTC mining objective active until explicit stop or fatal state.

    ``max_rounds`` exists only to make bounded diagnostics/tests possible.  Production
    callers leave it ``None`` so nonce exhaustion, stale work, rejected candidates and
    transient RPC failures all reconcile back into another work cycle automatically.
    """
    if not payout_script:
        raise LiveMinerError("payout_script is required before any coinbase is built")
    cfg = config or LiveMinerConfig()
    _validate_config(cfg)
    if max_rounds is not None and max_rounds < 0:
        raise LiveMinerError("max_rounds cannot be negative")

    lifecycle_stop = stop_event if stop_event is not None else Event()
    rounds = 0
    templates = 0
    stale_cancellations = 0
    nonce_exhaustions = 0
    candidates = 0
    submissions = 0
    accepted = 0
    rejected = 0
    transient_errors = 0
    extranonce_counter = 0
    retry_delay = cfg.retry_initial_seconds
    last_height: int | None = None
    last_block_hash_display: str | None = None

    def emit(kind: str, **detail: object) -> None:
        if on_event is not None:
            on_event({"event": kind, **detail})

    while not lifecycle_stop.is_set():
        if max_rounds is not None and rounds >= max_rounds:
            break

        round_stop = Event()
        watcher: Thread | None = None
        watcher_state: dict[str, str] = {}
        try:
            chain = _validate_chain(client.getblockchaininfo(), cfg)
            template = parse_block_template(client.getblocktemplate(list(cfg.rules)))
            templates += 1
            last_height = template.height
            current_tip_internal = hash_to_internal(client.getbestblockhash())

            if current_tip_internal != template.prev_hash_internal:
                rounds += 1
                stale_cancellations += 1
                extranonce_counter += 1
                emit("STALE_BEFORE_HASH", height=template.height, chain=chain, round=rounds)
                continue

            total_fees = _total_fees(template)
            watcher = Thread(
                target=_watch_tip,
                args=(client, template.prev_hash_internal, round_stop, lifecycle_stop, cfg.stale_poll_seconds, watcher_state),
                name="kex-btc-stale-tip-watch",
                daemon=True,
            )
            watcher.start()

            emit(
                "HASH_ROUND_STARTED",
                height=template.height,
                chain=chain,
                worker_count=cfg.worker_count,
                extranonce_counter=extranonce_counter,
            )
            result = run_pipeline(
                template=template,
                payout_script=payout_script,
                current_tip_internal=current_tip_internal,
                extranonce=_round_extranonce(cfg.extranonce, extranonce_counter),
                max_nonce_scan=cfg.max_nonce_scan,
                total_fees=total_fees,
                worker_count=cfg.worker_count,
                stop_event=round_stop,
            )
            rounds += 1
            extranonce_counter += 1
            retry_delay = cfg.retry_initial_seconds

            if lifecycle_stop.is_set() or watcher_state.get("reason") == "explicit_stop":
                emit("EXPLICIT_STOP", round=rounds)
                break

            if watcher_state.get("reason") == "stale_tip" or result.stale or result.cancelled:
                stale_cancellations += 1
                emit("STALE_HASH_CANCELLED", height=template.height, round=rounds)
                continue

            if result.winning_nonce is None or result.block_bytes is None:
                nonce_exhaustions += 1
                emit(
                    "NONCE_WINDOW_EXHAUSTED",
                    height=template.height,
                    round=rounds,
                    next_extranonce_counter=extranonce_counter,
                )
                continue

            candidates += 1
            last_block_hash_display = result.block_hash_display

            pre_submit_tip = hash_to_internal(client.getbestblockhash())
            if pre_submit_tip != template.prev_hash_internal:
                stale_cancellations += 1
                emit(
                    "CANDIDATE_DISCARDED_STALE",
                    height=template.height,
                    block_hash=result.block_hash_display,
                    round=rounds,
                )
                continue

            if not submit:
                emit(
                    "CANDIDATE_NO_SUBMIT",
                    height=template.height,
                    block_hash=result.block_hash_display,
                    round=rounds,
                )
                continue

            raw = client.submitblock(result.block_bytes.hex())
            submit_result = interpret_submitblock_response({"result": raw})
            submissions += 1
            if submit_result.accepted:
                accepted += 1
                emit(
                    "BLOCK_ACCEPTED",
                    height=template.height,
                    block_hash=result.block_hash_display,
                    round=rounds,
                )
            else:
                rejected += 1
                emit(
                    "BLOCK_REJECTED",
                    height=template.height,
                    block_hash=result.block_hash_display,
                    reject_reason=submit_result.reject_reason,
                    round=rounds,
                )

        except LiveMinerError:
            raise
        except (RpcError, OSError) as exc:
            transient_errors += 1
            emit(
                "TRANSIENT_RPC_ERROR",
                error=str(exc),
                retry_seconds=retry_delay,
                transient_errors=transient_errors,
            )
            if lifecycle_stop.wait(retry_delay):
                break
            retry_delay = min(
                cfg.retry_max_seconds,
                max(cfg.retry_initial_seconds, retry_delay * 2 if retry_delay else 0),
            )
        finally:
            round_stop.set()
            if watcher is not None:
                watcher.join(timeout=max(1.0, cfg.stale_poll_seconds * 2))

    return LifecycleSummary(
        rounds=rounds,
        templates=templates,
        stale_cancellations=stale_cancellations,
        nonce_exhaustions=nonce_exhaustions,
        candidates=candidates,
        submissions=submissions,
        accepted=accepted,
        rejected=rejected,
        transient_errors=transient_errors,
        stopped=lifecycle_stop.is_set(),
        last_height=last_height,
        last_block_hash_display=last_block_hash_display,
    )
