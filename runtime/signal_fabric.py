from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

ABI_VERSION = "kex.signal/1"
GENESIS = "GENESIS_0000000000000000"
ALLOWED_PHASES = ("VERIFY", "ADDRESS", "PROPAGATE", "EXECUTE", "COMMIT", "RECEIPT")
KNOWN_INVARIANTS = {"state_must_be_object", "no_null_state"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def atomic_write_json(path: str | Path, data: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        dir_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


@dataclass(frozen=True)
class SignalRequest:
    signal_id: str
    source: str
    target: str
    operation: str
    state_hash_before: str
    compiled_payload: Dict[str, Any]
    invariants: tuple[str, ...]
    authority: str
    sequence: int
    proof_root: str
    abi: str = ABI_VERSION

    @classmethod
    def compile(
        cls,
        *,
        source: str,
        target: str,
        operation: str,
        state: Mapping[str, Any],
        payload: Mapping[str, Any],
        invariants: Iterable[str],
        authority: str,
        sequence: int,
        previous_receipt: str = GENESIS,
    ) -> "SignalRequest":
        if not source or not target or not operation or not authority:
            raise ValueError("source, target, operation and authority are mandatory")
        if sequence < 1:
            raise ValueError("sequence must be >= 1")
        invariant_tuple = tuple(invariants)
        unknown = sorted(set(invariant_tuple) - KNOWN_INVARIANTS)
        if unknown:
            raise ValueError(f"UNKNOWN_INVARIANT:{','.join(unknown)}")
        state_hash = sha256_hex(canonical_json(state))
        compiled = dict(payload)
        proof_material = {
            "abi": ABI_VERSION,
            "source": source,
            "target": target,
            "operation": operation,
            "state_hash_before": state_hash,
            "compiled_payload": compiled,
            "invariants": list(invariant_tuple),
            "authority": authority,
            "sequence": sequence,
            "previous_receipt": previous_receipt,
        }
        proof_root = sha256_hex(canonical_json(proof_material))
        signal_id = f"sig_{sequence}_{proof_root[:24]}"
        return cls(signal_id, source, target, operation, state_hash, compiled, invariant_tuple, authority, sequence, proof_root)

    def verify_integrity(self, *, previous_receipt: str = GENESIS) -> bool:
        if self.abi != ABI_VERSION or set(self.invariants) - KNOWN_INVARIANTS:
            return False
        material = {
            "abi": self.abi,
            "source": self.source,
            "target": self.target,
            "operation": self.operation,
            "state_hash_before": self.state_hash_before,
            "compiled_payload": self.compiled_payload,
            "invariants": list(self.invariants),
            "authority": self.authority,
            "sequence": self.sequence,
            "previous_receipt": previous_receipt,
        }
        root = sha256_hex(canonical_json(material))
        return self.proof_root == root and self.signal_id == f"sig_{self.sequence}_{root[:24]}"


@dataclass(frozen=True)
class SignalReceipt:
    signal_id: str
    sequence: int
    status: str
    phase: str
    state_hash_before: str
    state_hash_after: str
    result: Dict[str, Any]
    previous_receipt: str
    request_proof_root: str
    receipt_hash: str
    committed_at_ns: int


class SignalRuntime:
    """Serialized per-target machine grammar with atomic state+receipt journaling."""

    def __init__(self, state_path: str | Path, receipt_path: str | Path):
        self.state_path = Path(state_path)
        self.receipt_path = Path(receipt_path)
        self.journal_path = self.state_path.parent / "signal_transaction.json"
        self.handlers: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def register(self, operation: str, handler: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]) -> None:
        if not operation:
            raise ValueError("operation required")
        self.handlers[operation] = handler

    def _read_journal(self) -> Dict[str, Any]:
        if not self.journal_path.exists():
            return {"state": {}, "head_receipt": GENESIS, "head_sequence": 0, "receipts": {}}
        data = json.loads(self.journal_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("state"), dict) or not isinstance(data.get("receipts", {}), dict):
            raise ValueError("JOURNAL_CORRUPTION")
        return {
            "state": data["state"],
            "head_receipt": data.get("head_receipt", GENESIS),
            "head_sequence": int(data.get("head_sequence", 0)),
            "receipts": data.get("receipts", {}),
        }

    def _read_state(self) -> Dict[str, Any]:
        return dict(self._read_journal()["state"])

    def _previous_receipt(self) -> str:
        return str(self._read_journal()["head_receipt"])

    def get_receipt(self, signal_id: str) -> SignalReceipt | None:
        raw = self._read_journal()["receipts"].get(signal_id)
        return SignalReceipt(**raw) if isinstance(raw, dict) else None

    def execute(self, request: SignalRequest) -> SignalReceipt:
        with self._lock:
            journal = self._read_journal()
            cached = journal["receipts"].get(request.signal_id)
            if isinstance(cached, dict):
                if cached.get("request_proof_root") != request.proof_root:
                    raise ValueError("DUPLICATE_SIGNAL_MISMATCH")
                return SignalReceipt(**cached)

            previous_receipt = str(journal["head_receipt"])
            expected_sequence = int(journal["head_sequence"]) + 1
            if request.sequence != expected_sequence:
                raise ValueError(f"SEQUENCE_PRECONDITION_FAILED expected={expected_sequence} actual={request.sequence}")
            if not request.verify_integrity(previous_receipt=previous_receipt):
                raise ValueError("SIGNAL_INTEGRITY_FAILURE")

            current = dict(journal["state"])
            current_hash = sha256_hex(canonical_json(current))
            if request.state_hash_before != current_hash:
                raise ValueError(f"STATE_PRECONDITION_FAILED expected={request.state_hash_before} actual={current_hash}")

            handler = self.handlers.get(request.operation)
            if handler is None:
                raise KeyError(f"UNBOUND_OPERATION:{request.operation}")
            next_state = handler(dict(current), dict(request.compiled_payload))
            if not isinstance(next_state, dict):
                raise TypeError("handler must return a dict state")

            for invariant in request.invariants:
                if invariant not in KNOWN_INVARIANTS:
                    raise ValueError(f"UNKNOWN_INVARIANT:{invariant}")
                if invariant == "state_must_be_object" and not isinstance(next_state, dict):
                    raise ValueError("INVARIANT_FAILED:state_must_be_object")
                if invariant == "no_null_state" and next_state is None:
                    raise ValueError("INVARIANT_FAILED:no_null_state")

            after_hash = sha256_hex(canonical_json(next_state))
            material = {
                "signal_id": request.signal_id,
                "sequence": request.sequence,
                "status": "COMMITTED",
                "phase": "RECEIPT",
                "state_hash_before": current_hash,
                "state_hash_after": after_hash,
                "result": next_state,
                "previous_receipt": previous_receipt,
                "request_proof_root": request.proof_root,
            }
            receipt_hash = sha256_hex(canonical_json(material))
            receipt = SignalReceipt(**material, receipt_hash=receipt_hash, committed_at_ns=time.time_ns())

            receipts = dict(journal["receipts"])
            receipts[request.signal_id] = asdict(receipt)
            if len(receipts) > 256:
                oldest = sorted(receipts.values(), key=lambda item: int(item.get("committed_at_ns", 0)))[:-256]
                for item in oldest:
                    receipts.pop(str(item["signal_id"]), None)

            atomic_write_json(self.journal_path, {
                "state": next_state,
                "head_receipt": receipt.receipt_hash,
                "head_sequence": receipt.sequence,
                "receipts": receipts,
            })
            return receipt


def default_mutation_handler(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    patch = payload.get("patch")
    if not isinstance(patch, dict):
        raise ValueError("payload.patch must be an object")
    state.update(patch)
    return state
