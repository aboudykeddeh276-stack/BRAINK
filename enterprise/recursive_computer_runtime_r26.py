from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import json

from enterprise.self_addressing_runtime import SelfAddressingRuntime
from runtime.R25.system_evolution_runtime import AppendOnlyLedger, canonical_json, sha256_json


def _copy(value: Any) -> Any:
    return json.loads(canonical_json(value))


@dataclass(frozen=True)
class ComputerIdentity:
    computer_id: str
    parent_id: str | None
    generation: int
    lineage: tuple[str, ...]
    constructor_id: str


class RecursiveComputer:
    """Constructor-bearing KEX computer composed from existing R25 mechanics.

    The object reuses SelfAddressingRuntime for logical/backing resolution,
    persistence and checkpoints, and the R25 append-only ledger for proof-bound
    transitions. Descendants inherit state, memory, lineage and constructor
    authority, so a child can instantiate its own successor.
    """

    CONSTRUCTOR_ID = "constructor://kex/recursive-computer/r26"

    def __init__(
        self,
        *,
        computer_id: str,
        state_root: str | Path,
        parent_id: str | None = None,
        generation: int = 0,
        lineage: tuple[str, ...] | None = None,
        state: Mapping[str, Any] | None = None,
        memory: Mapping[str, Any] | None = None,
    ) -> None:
        lineage = lineage or (computer_id,)
        self.identity = ComputerIdentity(
            computer_id=computer_id,
            parent_id=parent_id,
            generation=generation,
            lineage=tuple(lineage),
            constructor_id=self.CONSTRUCTOR_ID,
        )
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.runtime = SelfAddressingRuntime(self.state_root / "runtime-checkpoint.json")
        self.ledger = AppendOnlyLedger()
        self.state: dict[str, Any] = _copy(dict(state or {}))
        self.memory: dict[str, Any] = _copy(dict(memory or {}))
        self.children: dict[str, RecursiveComputer] = {}
        self._persist("BOOTSTRAP")

    def _snapshot(self) -> dict[str, Any]:
        # Canonicalize before persistence so in-memory tuples and their JSON
        # representation cannot create a false readback mismatch.
        return _copy(
            {
                "identity": asdict(self.identity),
                "state": self.state,
                "memory": self.memory,
                "children": sorted(self.children),
                "constructor": self.CONSTRUCTOR_ID,
            }
        )

    def _persist(self, operation: str) -> dict[str, Any]:
        snap = self._snapshot()
        backing = f"file://{self.state_root / 'computer.json'}"
        result = self.runtime.route(
            f"computer://{self.identity.computer_id}/state",
            backing,
            "WRITE",
            snap,
        )
        if result.get("status") != "COMMITTED":
            raise RuntimeError(f"PERSIST_FAILED:{result}")
        readback = self.runtime.route(
            f"computer://{self.identity.computer_id}/state",
            backing,
            "READ",
        )
        if readback.get("status") != "READ" or readback.get("value") != snap:
            raise RuntimeError("READBACK_MISMATCH")
        self.ledger.append(
            operation=operation,
            actor=self.identity.computer_id,
            owner="A.KEDDEH / KEDDEH_SYSTEMS",
            input_state=snap,
            output_state=readback["value"],
            proof={"readback_equal": True, "value_hash": readback["value_hash"]},
            rollback={"checkpoint": self.runtime.checkpoint()},
            lineage=self.identity.lineage,
        )
        return readback

    def write_state(self, key: str, value: Any) -> dict[str, Any]:
        before = self._snapshot()
        self.state[key] = _copy(value)
        readback = self._persist("STATE_WRITE")
        return {"before_root": sha256_json(before), "after_root": sha256_json(readback["value"])}

    def write_memory(self, key: str, value: Any) -> dict[str, Any]:
        before = self._snapshot()
        self.memory[key] = _copy(value)
        readback = self._persist("MEMORY_WRITE")
        return {"before_root": sha256_json(before), "after_root": sha256_json(readback["value"])}

    def instantiate(self, child_id: str) -> "RecursiveComputer":
        if child_id in self.children:
            raise ValueError("CHILD_ALREADY_EXISTS")
        child = RecursiveComputer(
            computer_id=child_id,
            state_root=self.state_root / "descendants" / child_id,
            parent_id=self.identity.computer_id,
            generation=self.identity.generation + 1,
            lineage=self.identity.lineage + (child_id,),
            state=self.state,
            memory=self.memory,
        )
        self.children[child_id] = child
        self._persist("SUCCESSOR_CREATED")
        return child

    def verify_constructor_continuity(self) -> dict[str, Any]:
        descendants = [self, *self.children.values()]
        valid = all(node.identity.constructor_id == self.CONSTRUCTOR_ID for node in descendants)
        return {
            "status": "VERIFIED" if valid else "FAILED",
            "constructor_id": self.CONSTRUCTOR_ID,
            "nodes": [node.identity.computer_id for node in descendants],
        }

    def readback(self) -> dict[str, Any]:
        backing = f"file://{self.state_root / 'computer.json'}"
        result = self.runtime.route(
            f"computer://{self.identity.computer_id}/state",
            backing,
            "READ",
        )
        if result.get("status") != "READ":
            raise RuntimeError(f"READBACK_FAILED:{result}")
        return result["value"]


def execute_recursive_proof(root_dir: str | Path) -> dict[str, Any]:
    """Execute the A -> B -> C recursive constructor proof."""
    root = RecursiveComputer(computer_id="A", state_root=Path(root_dir) / "A")
    root.write_memory("seed", 297)
    root.write_state("phase", "ROOT_READY")

    child = root.instantiate("B")
    child.write_memory("child", 88)
    child.write_state("phase", "CHILD_READY")

    grandchild = child.instantiate("C")
    grandchild.write_state("phase", "GRANDCHILD_READY")

    rb_a = root.readback()
    rb_b = child.readback()
    rb_c = grandchild.readback()

    proof = {
        "status": "VERIFIED",
        "lineage": {
            "A": list(root.identity.lineage),
            "B": list(child.identity.lineage),
            "C": list(grandchild.identity.lineage),
        },
        "memory": {
            "A": rb_a["memory"],
            "B": rb_b["memory"],
            "C": rb_c["memory"],
        },
        "constructor_ids": {
            "A": root.identity.constructor_id,
            "B": child.identity.constructor_id,
            "C": grandchild.identity.constructor_id,
        },
        "state_roots": {
            "A": sha256_json(rb_a),
            "B": sha256_json(rb_b),
            "C": sha256_json(rb_c),
        },
        "ledger_verified": {
            "A": root.ledger.verify(),
            "B": child.ledger.verify(),
            "C": grandchild.ledger.verify(),
        },
    }
    if rb_b["memory"].get("seed") != 297:
        raise RuntimeError("B_DID_NOT_INHERIT_ROOT_MEMORY")
    if rb_c["memory"].get("seed") != 297 or rb_c["memory"].get("child") != 88:
        raise RuntimeError("C_DID_NOT_INHERIT_TRANSITIVE_MEMORY")
    if len({*proof["constructor_ids"].values()}) != 1:
        raise RuntimeError("CONSTRUCTOR_CONTINUITY_FAILED")
    if not all(proof["ledger_verified"].values()):
        raise RuntimeError("LEDGER_VERIFICATION_FAILED")
    return proof
