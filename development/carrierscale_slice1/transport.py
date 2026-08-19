"""CarrierScale Slice-1 arbitrary-byte transport.

This module deliberately implements only the transport contract.  It does not
claim Linux boot, guest execution, or external delivery.  A concrete guest
adapter must consume frames and return an acknowledgement before a transfer can
be promoted to RUNTIME_OBSERVED.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable
import struct
import time

MAGIC = b"KXCS"
VERSION = 1
HEADER = struct.Struct(">4sB16sII32s")
DEFAULT_MAX_PAYLOAD = 16 * 1024 * 1024
DEFAULT_FRAME_SIZE = 64 * 1024


class TransportError(ValueError):
    """Raised when a frame or transfer violates the Slice-1 contract."""


@dataclass(frozen=True)
class TransferReceipt:
    transfer_id: str
    byte_count: int
    frame_count: int
    input_sha256: str
    output_sha256: str
    started_ns: int
    completed_ns: int
    result: str

    @property
    def verified(self) -> bool:
        return self.result == "VERIFIED" and self.input_sha256 == self.output_sha256


def _transfer_token(transfer_id: str) -> bytes:
    raw = transfer_id.encode("utf-8")
    return sha256(raw).digest()[:16]


def frame_payload(
    payload: bytes,
    *,
    transfer_id: str,
    frame_size: int = DEFAULT_FRAME_SIZE,
    max_payload: int = DEFAULT_MAX_PAYLOAD,
) -> list[bytes]:
    """Encode arbitrary bytes into bounded, independently checked frames."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not transfer_id:
        raise TransportError("transfer_id is required")
    if frame_size <= 0:
        raise TransportError("frame_size must be positive")
    if len(payload) > max_payload:
        raise TransportError("payload exceeds configured maximum")

    chunks = [payload[i : i + frame_size] for i in range(0, len(payload), frame_size)] or [b""]
    total = len(chunks)
    token = _transfer_token(transfer_id)
    frames: list[bytes] = []
    for index, chunk in enumerate(chunks):
        digest = sha256(chunk).digest()
        frames.append(HEADER.pack(MAGIC, VERSION, token, index, total, digest) + chunk)
    return frames


def reassemble_frames(
    frames: Iterable[bytes],
    *,
    transfer_id: str,
    max_payload: int = DEFAULT_MAX_PAYLOAD,
) -> bytes:
    """Validate and reconstruct one transfer without interpreting its bytes."""
    expected_token = _transfer_token(transfer_id)
    decoded: dict[int, bytes] = {}
    expected_total: int | None = None
    size = 0

    for frame in frames:
        if len(frame) < HEADER.size:
            raise TransportError("truncated frame")
        magic, version, token, index, total, digest = HEADER.unpack(frame[: HEADER.size])
        chunk = frame[HEADER.size :]
        if magic != MAGIC or version != VERSION:
            raise TransportError("unsupported frame format")
        if token != expected_token:
            raise TransportError("transfer identity mismatch")
        if total == 0 or index >= total:
            raise TransportError("invalid frame index")
        if sha256(chunk).digest() != digest:
            raise TransportError("frame digest mismatch")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise TransportError("inconsistent frame count")
        if index in decoded:
            raise TransportError("duplicate frame")
        size += len(chunk)
        if size > max_payload:
            raise TransportError("reassembled payload exceeds configured maximum")
        decoded[index] = chunk

    if expected_total is None:
        raise TransportError("no frames supplied")
    if len(decoded) != expected_total:
        raise TransportError("incomplete transfer")
    return b"".join(decoded[i] for i in range(expected_total))


def verify_round_trip(payload: bytes, *, transfer_id: str) -> TransferReceipt:
    """Model-local conformance proof; not evidence of a real guest boundary."""
    started = time.time_ns()
    frames = frame_payload(payload, transfer_id=transfer_id)
    output = reassemble_frames(frames, transfer_id=transfer_id)
    completed = time.time_ns()
    before = sha256(payload).hexdigest()
    after = sha256(output).hexdigest()
    return TransferReceipt(
        transfer_id=transfer_id,
        byte_count=len(payload),
        frame_count=len(frames),
        input_sha256=before,
        output_sha256=after,
        started_ns=started,
        completed_ns=completed,
        result="VERIFIED" if before == after else "FAILED",
    )
