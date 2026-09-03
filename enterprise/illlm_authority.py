from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable
import hashlib, json, os, time


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorityBinding:
    intent: str
    function_id: str
    process_id: str
    runtime_action: str
    mutating: bool


class ILLLMAuthority:
    """Deterministic IL-LLM resolver and dispatcher.

    IL-LLM resolves governed input to an allowed function/process binding.
    KEX runtime authority remains the only state-mutation authority.
    """

    AUTHORITY_ID = "authority://illlm/keddeh"
    RUNTIME_ID = "illlm://keddeh/runtime"
    SCHEMA = "illlm.authority.execution.v1"

    DEFAULT_BINDINGS = {
        "state.write": AuthorityBinding("state.write", "function://illlm/kex/state-write", "process://illlm/kex/state-write", "write_state", True),
        "memory.write": AuthorityBinding("memory.write", "function://illlm/kex/memory-write", "process://illlm/kex/memory-write", "write_memory", True),
        "computer.instantiate": AuthorityBinding("computer.instantiate", "function://illlm/kex/instantiate", "process://illlm/kex/instantiate", "instantiate", True),
        "computer.read": AuthorityBinding("computer.read", "function://illlm/kex/read", "process://illlm/kex/read", "snapshot", False),
    }

    def __init__(self, receipt_path: str | Path, bindings: dict[str, AuthorityBinding] | None = None):
        self.receipt_path = Path(receipt_path)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.bindings = dict(bindings or self.DEFAULT_BINDINGS)

    @staticmethod
    def normalize(request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ValueError("ILLLM_REQUEST_MUST_BE_OBJECT")
        intent = str(request.get("intent", "")).strip().lower()
        lineage = request.get("lineage", "A")
        if isinstance(lineage, (list, tuple)):
            lineage = "/".join(str(x) for x in lineage)
        normalized = {"intent": intent, "lineage": str(lineage).strip()}
        if "key" in request:
            normalized["key"] = str(request["key"])
        if "value" in request:
            normalized["value"] = request["value"]
        if "child_id" in request:
            normalized["child_id"] = str(request["child_id"])
        return normalized

    def resolve(self, request: dict[str, Any]) -> tuple[dict[str, Any], AuthorityBinding]:
        normalized = self.normalize(request)
        binding = self.bindings.get(normalized["intent"])
        if binding is None:
            raise ValueError("ILLLM_UNRESOLVED_INTENT")
        if not normalized["lineage"]:
            raise ValueError("ILLLM_LINEAGE_REQUIRED")
        if binding.intent in {"state.write", "memory.write"} and "key" not in normalized:
            raise ValueError("ILLLM_KEY_REQUIRED")
        if binding.intent == "computer.instantiate" and not normalized.get("child_id"):
            raise ValueError("ILLLM_CHILD_ID_REQUIRED")
        return normalized, binding

    def _append_receipt(self, receipt: dict[str, Any]) -> None:
        existing = []
        if self.receipt_path.exists():
            existing = json.loads(self.receipt_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                raise RuntimeError("ILLLM_RECEIPT_LEDGER_INVALID")
        previous = existing[-1]["receipt_id"] if existing else None
        body = dict(receipt)
        body["sequence"] = len(existing) + 1
        body["previous_receipt"] = previous
        body["receipt_id"] = root(body)
        existing.append(body)
        tmp = self.receipt_path.with_suffix(self.receipt_path.suffix + ".tmp")
        raw = (json.dumps(existing, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with tmp.open("wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.receipt_path)
        fd = os.open(self.receipt_path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def verify_receipts(self) -> bool:
        if not self.receipt_path.exists():
            return True
        events = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        previous = None
        for index, event in enumerate(events, start=1):
            candidate = dict(event)
            claimed = candidate.pop("receipt_id", None)
            if candidate.get("sequence") != index or candidate.get("previous_receipt") != previous:
                return False
            if root(candidate) != claimed:
                return False
            previous = claimed
        return True

    def execute(self, request: dict[str, Any], runtime_host: Any) -> dict[str, Any]:
        normalized, binding = self.resolve(request)
        pre = runtime_host.snapshot(runtime_host.resolve(normalized["lineage"]))
        action: Callable[..., Any] = getattr(runtime_host, binding.runtime_action)
        if binding.intent == "state.write":
            result = action(normalized["lineage"], normalized["key"], normalized.get("value"))
        elif binding.intent == "memory.write":
            result = action(normalized["lineage"], normalized["key"], normalized.get("value"))
        elif binding.intent == "computer.instantiate":
            result = action(normalized["lineage"], normalized["child_id"])
        elif binding.intent == "computer.read":
            result = action(runtime_host.resolve(normalized["lineage"]))
        else:
            raise RuntimeError("ILLLM_BINDING_RUNTIME_ACTION_UNIMPLEMENTED")
        receipt = {
            "schema": self.SCHEMA,
            "authority_id": self.AUTHORITY_ID,
            "illlm_runtime_id": self.RUNTIME_ID,
            "input_root": root(request),
            "normalized": normalized,
            "normalized_root": root(normalized),
            "index_resolution": f"index://illlm/kex/{binding.intent}",
            "function_id": binding.function_id,
            "process_id": binding.process_id,
            "runtime_authority": "runtime://kex/runtime",
            "runtime_action": binding.runtime_action,
            "mutating": binding.mutating,
            "pre_state_root": root(pre),
            "post_state_root": root(result),
            "runtime_readback_verified": bool(result.get("ledger_verified", False)),
            "timestamp_ns": time.time_ns(),
        }
        self._append_receipt(receipt)
        if not self.verify_receipts():
            raise RuntimeError("ILLLM_RECEIPT_READBACK_FAILED")
        return {
            "status": "EXECUTED",
            "authority": asdict(binding),
            "result": result,
            "receipt_ledger": str(self.receipt_path),
            "receipt_ledger_verified": True,
        }
