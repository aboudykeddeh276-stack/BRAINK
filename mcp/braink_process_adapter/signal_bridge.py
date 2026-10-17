from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable, Mapping

from runtime.signal_fabric import GENESIS, SignalRequest


class WindowSignalBridge:
    """Compiles agent/window intent into the shared machine propagation ABI."""

    def __init__(self, source_identity: str, target_identity: str, authority: str):
        self.source_identity = source_identity
        self.target_identity = target_identity
        self.authority = authority
        self.sequence = 0
        self.previous_receipt = GENESIS

    def compile(
        self,
        *,
        operation: str,
        authoritative_state: Mapping[str, Any],
        payload: Mapping[str, Any],
        invariants: Iterable[str] = ("state_must_be_object", "no_null_state"),
    ) -> Dict[str, Any]:
        self.sequence += 1
        request = SignalRequest.compile(
            source=self.source_identity,
            target=self.target_identity,
            operation=operation,
            state=authoritative_state,
            payload=payload,
            invariants=invariants,
            authority=self.authority,
            sequence=self.sequence,
            previous_receipt=self.previous_receipt,
        )
        return asdict(request)

    def accept_receipt(self, receipt: Mapping[str, Any]) -> None:
        if receipt.get("status") != "COMMITTED" or receipt.get("phase") != "RECEIPT":
            raise ValueError("receipt is not a committed machine receipt")
        receipt_hash = receipt.get("receipt_hash")
        if not isinstance(receipt_hash, str) or len(receipt_hash) != 64:
            raise ValueError("invalid receipt hash")
        self.previous_receipt = receipt_hash
