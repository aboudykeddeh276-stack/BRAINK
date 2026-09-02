from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional
import hashlib, json, time


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _root(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


@dataclass
class SectorBinding:
    sector: str
    mechanic: str
    handler: Optional[Callable[[dict], dict]] = None
    execution_repo: Optional[str] = None


class CrossSectorExecutor:
    """Execute a routed work envelope only through explicitly bound sector mechanics.

    No handler means UNBOUND, not failure and not fake execution. A successful handler must return
    observed state; the executor then appends a receipt and advances the envelope epoch.
    """
    def __init__(self):
        self.bindings: Dict[str, SectorBinding] = {}

    def bind(self, sector: str, mechanic: str, handler: Callable[[dict], dict], execution_repo: Optional[str] = None):
        self.bindings[sector] = SectorBinding(sector, mechanic, handler, execution_repo)

    def describe(self, sector: str) -> dict:
        b = self.bindings.get(sector)
        if not b:
            return {"sector": sector, "state": "UNBOUND"}
        return {"sector": sector, "state": "BOUND", "mechanic": b.mechanic, "execution_repo": b.execution_repo}

    def execute(self, sector: str, envelope: dict) -> dict:
        binding = self.bindings.get(sector)
        if not binding or not binding.handler:
            return {"state": "UNBOUND", "sector": sector, "envelope": envelope}
        before_root = envelope.get("envelope_root")
        started = time.time_ns()
        observed = binding.handler(envelope)
        if not isinstance(observed, dict):
            raise TypeError("sector handler must return observed state dict")
        receipt = {
            "sector": sector,
            "mechanic": binding.mechanic,
            "execution_repo": binding.execution_repo,
            "before_root": before_root,
            "observed": observed,
            "started_ns": started,
            "completed_ns": time.time_ns(),
        }
        receipt["receipt_root"] = _root(receipt)
        out = json.loads(json.dumps(envelope))
        out.setdefault("evidence", []).append(receipt)
        out.setdefault("state", {}).setdefault("sector_readback", {})[sector] = observed
        out.setdefault("continuation", {})["epoch"] = int(out.get("continuation", {}).get("epoch", 0)) + 1
        out["continuation"]["status"] = "READ_BACK"
        out["envelope_root"] = _root({k: v for k, v in out.items() if k != "envelope_root"})
        return {"state": "READ_BACK", "sector": sector, "receipt": receipt, "envelope": out}
