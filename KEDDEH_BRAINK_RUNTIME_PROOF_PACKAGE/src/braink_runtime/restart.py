"""Restart, crash simulation and recovery proof."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .ledger import GENESIS_HASH, Ledger

__all__ = ["RestartState", "RestartManager"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RestartState:
    session_id: str
    last_entry_id: int
    last_entry_hash: str
    ledger_path: str
    timestamp: str
    clean_shutdown: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RestartState":
        return RestartState(
            session_id=data["session_id"],
            last_entry_id=int(data["last_entry_id"]),
            last_entry_hash=data["last_entry_hash"],
            ledger_path=data["ledger_path"],
            timestamp=data["timestamp"],
            clean_shutdown=bool(data.get("clean_shutdown", False)),
        )


class RestartManager:
    """Persists a small restart marker and proves recovery against the ledger."""

    def __init__(self, state_path: str, ledger_path: str, session_id: str = None) -> None:
        if not state_path:
            raise ValueError("state_path must be provided")
        if not ledger_path:
            raise ValueError("ledger_path must be provided")
        self.state_path = state_path
        self.ledger_path = ledger_path
        self.session_id = session_id or uuid.uuid4().hex

    def save_state(self, ledger: Ledger, clean: bool = True) -> RestartState:
        state = RestartState(
            session_id=self.session_id,
            last_entry_id=ledger.head_id(),
            last_entry_hash=ledger.head_hash(),
            ledger_path=self.ledger_path,
            timestamp=_utc_now(),
            clean_shutdown=clean,
        )
        directory = os.path.dirname(os.path.abspath(self.state_path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state.to_dict(), handle, indent=2, sort_keys=True)
        return state

    def load_state(self) -> Optional[RestartState]:
        if not os.path.exists(self.state_path):
            return None
        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (ValueError, OSError):
            return None
        try:
            return RestartState.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return None

    def simulate_unclean_shutdown(self, ledger: Ledger) -> Dict[str, Any]:
        """Append a crash marker and deliberately skip saving clean state."""
        entry = ledger.append(
            "CRASH_SIMULATED",
            {"session_id": self.session_id, "reason": "simulated unclean shutdown"},
        )
        return entry.to_dict()

    def recover(self, ledger: Ledger) -> Dict[str, Any]:
        """Verify the ledger against the saved marker and report."""
        state = self.load_state()
        chain_valid = ledger.verify_chain()
        tampered = ledger.detect_tamper()
        head_id = ledger.head_id()
        head_hash = ledger.head_hash()
        entries_since_state = (
            head_id - state.last_entry_id if state is not None else head_id
        )
        report = {
            "session_id": self.session_id,
            "recovered_at": _utc_now(),
            "state_found": state is not None,
            "clean_shutdown": state.clean_shutdown if state else False,
            "saved_entry_id": state.last_entry_id if state else 0,
            "saved_entry_hash": state.last_entry_hash if state else GENESIS_HASH,
            "current_entry_id": head_id,
            "current_entry_hash": head_hash,
            "entries_since_saved_state": entries_since_state,
            "chain_valid": chain_valid,
            "tampered_entries": tampered,
            "recovery_ok": chain_valid and not tampered,
            "status": "RESTART_TESTED" if chain_valid and not tampered else "RECOVERY_FAILED",
        }
        return report

    def generate_restart_receipt(
        self, ledger: Ledger, state: Optional[RestartState]
    ) -> Dict[str, Any]:
        recovery = self.recover(ledger)
        return {
            "receipt_type": "RESTART_PROOF",
            "session_id": self.session_id,
            "ledger_path": self.ledger_path,
            "state_path": self.state_path,
            "pre_restart_state": state.to_dict() if state else None,
            "post_restart_entry_id": ledger.head_id(),
            "post_restart_entry_hash": ledger.head_hash(),
            "entry_count": ledger.count(),
            "chain_valid": recovery["chain_valid"],
            "tampered_entries": recovery["tampered_entries"],
            "recovery_report": recovery,
            "continuity_proven": bool(
                state is not None
                and recovery["chain_valid"]
                and ledger.head_id() >= state.last_entry_id
            ),
            "generated_at": _utc_now(),
            "status": "RESTART_TESTED" if recovery["recovery_ok"] else "RECOVERY_FAILED",
        }
