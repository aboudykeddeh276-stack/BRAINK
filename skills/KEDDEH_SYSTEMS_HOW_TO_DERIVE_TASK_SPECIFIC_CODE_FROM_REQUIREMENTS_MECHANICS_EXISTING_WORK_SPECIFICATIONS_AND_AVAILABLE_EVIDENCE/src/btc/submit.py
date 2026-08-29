"""Mechanic: submitblock request construction (transport-free).

The `submitblock` RPC contract: params carry the hex-encoded serialized block; a
`null` result means accepted, a non-null string result is the reject reason. This
module derives the request object and interprets the response WITHOUT performing any
network I/O — the transport is a subordinate acquisition concern, not the mechanic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubmitResult:
    accepted: bool
    reject_reason: str | None


def build_submitblock_request(block_bytes: bytes, request_id: int = 1) -> dict:
    """Construct the JSON-RPC submitblock request object."""
    if not block_bytes:
        raise ValueError("block_bytes must be non-empty")
    return {
        "jsonrpc": "1.0",
        "id": request_id,
        "method": "submitblock",
        "params": [block_bytes.hex()],
    }


def interpret_submitblock_response(response: dict) -> SubmitResult:
    """Interpret a submitblock RPC response per its contract."""
    if "error" in response and response["error"]:
        raise ValueError(f"RPC error: {response['error']}")
    result = response.get("result")
    if result is None:
        return SubmitResult(accepted=True, reject_reason=None)
    return SubmitResult(accepted=False, reject_reason=str(result))
