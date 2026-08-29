"""Mechanic: Stratum V1 worker-boundary messages (transport-free).

Stratum is the correct place for public/remote worker access — NOT Core RPC. This
module builds and parses the four Stratum V1 methods used between a hashing worker
and the controller:

    mining.subscribe   worker -> server   (server replies extranonce1, extranonce2 size)
    mining.authorize   worker -> server   (worker credentials for this pool session)
    mining.notify      server -> worker   (the job: prevhash, coinbase parts, branches...)
    mining.submit      worker -> server   (found share: worker, job, extranonce2, ntime, nonce)

A job carries the previous hash, the two coinbase halves (so the worker splices its
own extranonce2), the Merkle branch, block version, nBits, nTime and the clean-jobs
flag. The worker needs only this — never wallet or RPC credentials — which is the
whole point of the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StratumJob:
    job_id: str
    prevhash_hex: str          # Stratum-encoded previous block hash
    coinb1_hex: str            # coinbase up to the extranonce2 insertion point
    coinb2_hex: str            # coinbase after the extranonce2 insertion point
    merkle_branch_hex: list[str]
    version_hex: str
    nbits_hex: str
    ntime_hex: str
    clean_jobs: bool = True


def build_subscribe_response(
    request_id: int, extranonce1_hex: str, extranonce2_size: int
) -> dict:
    """Server response to ``mining.subscribe`` (subscription + extranonce domain)."""
    if extranonce2_size < 0:
        raise ValueError("extranonce2_size must be non-negative")
    subscriptions = [["mining.set_difficulty", "1"], ["mining.notify", extranonce1_hex]]
    return {
        "id": request_id,
        "result": [subscriptions, extranonce1_hex, extranonce2_size],
        "error": None,
    }


def build_notify(job: StratumJob) -> dict:
    """Server ``mining.notify`` request carrying a full job to a worker."""
    return {
        "id": None,
        "method": "mining.notify",
        "params": [
            job.job_id,
            job.prevhash_hex,
            job.coinb1_hex,
            job.coinb2_hex,
            list(job.merkle_branch_hex),
            job.version_hex,
            job.nbits_hex,
            job.ntime_hex,
            job.clean_jobs,
        ],
    }


@dataclass(frozen=True)
class ShareSubmission:
    worker_name: str
    job_id: str
    extranonce2_hex: str
    ntime_hex: str
    nonce_hex: str
    version_bits_hex: str | None = None


def parse_submit(message: dict) -> ShareSubmission:
    """Parse a worker ``mining.submit`` message into a ShareSubmission."""
    if message.get("method") != "mining.submit":
        raise ValueError("not a mining.submit message")
    params = message.get("params") or []
    if len(params) < 5:
        raise ValueError("mining.submit requires at least 5 params")
    worker, job_id, extranonce2, ntime, nonce = params[:5]
    version_bits = params[5] if len(params) >= 6 else None
    return ShareSubmission(
        worker_name=str(worker),
        job_id=str(job_id),
        extranonce2_hex=str(extranonce2),
        ntime_hex=str(ntime),
        nonce_hex=str(nonce),
        version_bits_hex=str(version_bits) if version_bits is not None else None,
    )


def build_submit_response(request_id: int, accepted: bool, reject_reason: str | None = None) -> dict:
    """Server response to a ``mining.submit`` (accept/reject a share)."""
    if accepted:
        return {"id": request_id, "result": True, "error": None}
    reason = reject_reason or "rejected"
    # Stratum error tuple: [code, message, traceback]
    return {"id": request_id, "result": False, "error": [20, reason, None]}
