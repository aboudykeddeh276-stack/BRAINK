from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import json

from enterprise.self_addressing_runtime import SelfAddressingRuntime
from runtime.R25.system_evolution_runtime import (
    AppendOnlyLedger,
    TransactionReceipt,
    canonical_json,
    sha256_json,
)


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

    State and proof events are persisted through SelfAddressingRuntime-backed
    JSON objects. A persisted computer can warm-boot, retain constructor
    identity and instantiate a further descendant after process discontinuity.
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
        bootstrap: bool = True,
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
        if bootstrap:
            self._persist("BOOTSTRAP")

    @property
    def state_backing(self) -> str:
        return f"file://{self.state_root / 'computer.json'}"

    @property
    def ledger_backing(self) -> str:
        return f"file://{self.state_root / 'ledger.json'}"

    def _snapshot(self) -> dict[str, Any]:
        return _copy(
            {
                "identity": asdict(self.identity),
                "state": self.state,
                "memory": self.memory,
                "children": sorted(self.children),
                "constructor": self.CONSTRUCTOR_ID,
            }
        )

    def _persist_ledger(self) -> dict[str, Any]:
        events = [asdict(event) for event in self.ledger.events]
        result = self.runtime.route(
            f"computer://{self.identity.computer_id}/ledger",
            self.ledger_backing,
            "WRITE",
            events,
        )
        if result.get("status") != "COMMITTED":
            raise RuntimeError(f"LEDGER_PERSIST_FAILED:{result}")
        readback = self.runtime.route(
            f"computer://{self.identity.computer_id}/ledger",
            self.ledger_backing,
            "READ",
        )
        if readback.get("status") != "READ" or readback.get("value") != events:
            raise RuntimeError("LEDGER_READBACK_MISMATCH")
        return readback

    def _persist(self, operation: str) -> dict[str, Any]:
        snap = self._snapshot()
        result = self.runtime.route(
            f"computer://{self.identity.computer_id}/state",
            self.state_backing,
            "WRITE",
            snap,
        )
        if result.get("status") != "COMMITTED":
            raise RuntimeError(f"PERSIST_FAILED:{result}")
        readback = self.runtime.route(
            f"computer://{self.identity.computer_id}/state",
            self.state_backing,
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
        self._persist_ledger()
        return readback

    @classmethod
    def restore(cls, state_root: str | Path) -> "RecursiveComputer":
        state_root = Path(state_root)
        state_path = state_root / "computer.json"
        ledger_path = state_root / "ledger.json"
        if not state_path.exists():
            raise FileNotFoundError(state_path)
        snap = json.loads(state_path.read_text())
        identity = snap["identity"]
        if snap.get("constructor") != cls.CONSTRUCTOR_ID:
            raise RuntimeError("CONSTRUCTOR_ID_MISMATCH")
        computer = cls(
            computer_id=identity["computer_id"],
            state_root=state_root,
            parent_id=identity.get("parent_id"),
            generation=int(identity["generation"]),
            lineage=tuple(identity["lineage"]),
            state=snap.get("state", {}),
            memory=snap.get("memory", {}),
            bootstrap=False,
        )
        if ledger_path.exists():
            raw_events = json.loads(ledger_path.read_text())
            computer.ledger._events = [TransactionReceipt(**event) for event in raw_events]
            if not computer.ledger.verify():
                raise RuntimeError("RESTORED_LEDGER_INVALID")
        state_readback = computer.runtime.route(
            f"computer://{computer.identity.computer_id}/state",
            computer.state_backing,
            "READ",
        )
        if state_readback.get("status") != "READ" or state_readback.get("value") != snap:
            raise RuntimeError("RESTORE_STATE_READBACK_MISMATCH")
        computer.ledger.append(
            operation="WARM_BOOT_RESTORE",
            actor=computer.identity.computer_id,
            owner="A.KEDDEH / KEDDEH_SYSTEMS",
            input_state=snap,
            output_state=state_readback["value"],
            proof={"readback_equal": True, "restored": True},
            rollback={"checkpoint": computer.runtime.checkpoint()},
            lineage=computer.identity.lineage,
        )
        computer._persist_ledger()
        return computer

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

    def readback(self) -> dict[str, Any]:
        result = self.runtime.route(
            f"computer://{self.identity.computer_id}/state",
            self.state_backing,
            "READ",
        )
        if result.get("status") != "READ":
            raise RuntimeError(f"READBACK_FAILED:{result}")
        return result["value"]


def execute_recursive_proof(root_dir: str | Path) -> dict[str, Any]:
    """Execute A -> B -> C, warm-boot C, then let restored C create D."""
    root_dir = Path(root_dir)
    root = RecursiveComputer(computer_id="A", state_root=root_dir / "A")
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

    restored_c = RecursiveComputer.restore(root_dir / "A" / "descendants" / "B" / "descendants" / "C")
    descendant = restored_c.instantiate("D")
    descendant.write_state("phase", "POST_RESTORE_DESCENDANT_READY")
    rb_d = descendant.readback()

    proof = {
        "status": "VERIFIED",
        "lineage": {
            "A": list(root.identity.lineage),
            "B": list(child.identity.lineage),
            "C": list(grandchild.identity.lineage),
            "D": list(descendant.identity.lineage),
        },
        "memory": {
            "A": rb_a["memory"],
            "B": rb_b["memory"],
            "C": rb_c["memory"],
            "D": rb_d["memory"],
        },
        "constructor_ids": {
            "A": root.identity.constructor_id,
            "B": child.identity.constructor_id,
            "C": grandchild.identity.constructor_id,
            "restored_C": restored_c.identity.constructor_id,
            "D": descendant.identity.constructor_id,
        },
        "state_roots": {
            "A": sha256_json(rb_a),
            "B": sha256_json(rb_b),
            "C": sha256_json(rb_c),
            "D": sha256_json(rb_d),
        },
        "ledger_verified": {
            "A": root.ledger.verify(),
            "B": child.ledger.verify(),
            "C": grandchild.ledger.verify(),
            "restored_C": restored_c.ledger.verify(),
            "D": descendant.ledger.verify(),
        },
        "warm_boot": {
            "restored_computer": restored_c.identity.computer_id,
            "restored_lineage": list(restored_c.identity.lineage),
            "restored_memory": restored_c.memory,
            "post_restore_descendant": descendant.identity.computer_id,
        },
    }
    if rb_b["memory"].get("seed") != 297:
        raise RuntimeError("B_DID_NOT_INHERIT_ROOT_MEMORY")
    if rb_c["memory"].get("seed") != 297 or rb_c["memory"].get("child") != 88:
        raise RuntimeError("C_DID_NOT_INHERIT_TRANSITIVE_MEMORY")
    if restored_c.memory != rb_c["memory"]:
        raise RuntimeError("WARM_BOOT_MEMORY_MISMATCH")
    if rb_d["memory"].get("seed") != 297 or rb_d["memory"].get("child") != 88:
        raise RuntimeError("D_DID_NOT_INHERIT_RESTORED_MEMORY")
    if list(descendant.identity.lineage) != ["A", "B", "C", "D"]:
        raise RuntimeError("POST_RESTORE_LINEAGE_FAILED")
    if len({*proof["constructor_ids"].values()}) != 1:
        raise RuntimeError("CONSTRUCTOR_CONTINUITY_FAILED")
    if not all(proof["ledger_verified"].values()):
        raise RuntimeError("LEDGER_VERIFICATION_FAILED")
    return proof
