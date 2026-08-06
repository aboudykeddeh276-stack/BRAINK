"""BrAInK runtime orchestrator: wires every subsystem into one lifecycle."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from .dns_transport import DNSTransport
from .identity import IdentityRegistry, generate_component_id
from .ledger import Ledger
from .linguistic_core import LinguisticCore
from .restart import RestartManager, RestartState
from .signer import ProductionSignerPlaceholder, TestSigner

__all__ = ["BrAInKRuntime", "DEFAULT_NAMESPACE"]

DEFAULT_NAMESPACE = "braink"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrAInKRuntime:
    """Single entry point for the proof runtime.

    Config keys:
        ``ledger_path``   - sqlite file for the ledger (required in practice)
        ``state_path``    - restart marker file
        ``namespace``     - identity namespace, default ``braink``
        ``version``       - runtime version string
        ``session_id``    - optional explicit session id
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        if config is None or not isinstance(config, dict):
            raise ValueError("config must be a dict")
        self.config = dict(config)
        self.namespace = self.config.get("namespace", DEFAULT_NAMESPACE)
        self.version = self.config.get("version", "1.0.0")
        self.session_id = self.config.get("session_id") or uuid.uuid4().hex
        self.ledger_path = self.config.get("ledger_path") or os.path.join(
            os.getcwd(), "braink_ledger.sqlite"
        )
        self.state_path = self.config.get("state_path") or os.path.join(
            os.path.dirname(os.path.abspath(self.ledger_path)), "restart_state.json"
        )

        self.linguistic = LinguisticCore()
        self.identities = IdentityRegistry()
        self.ledger = Ledger(self.ledger_path)
        self.signer = TestSigner()
        self.production_signer = ProductionSignerPlaceholder()
        self.dns = DNSTransport()
        self.restart_manager = RestartManager(
            self.state_path, self.ledger_path, session_id=self.session_id
        )

        self.runtime_id = generate_component_id(self.namespace, "runtime", self.version)
        self.identities.register(
            self.runtime_id,
            {
                "kind": "component",
                "namespace": self.namespace,
                "name": "runtime",
                "version": self.version,
            },
        )
        self.started = False
        self.command_count = 0

    # -- lifecycle ------------------------------------------------------
    def start(self) -> Dict[str, Any]:
        payload = {
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "version": self.version,
            "lexicon_version": self.linguistic.lexicon_version(),
        }
        entry = self.ledger.append("RUNTIME_START", payload)
        envelope = self.signer.sign(payload)
        self.started = True
        return {
            "status": "STARTED",
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "entry_id": entry.entry_id,
            "entry_hash": entry.entry_hash,
            "signature": envelope.to_dict(),
            "started_at": _utc_now(),
        }

    def process_command(self, text: str) -> Dict[str, Any]:
        if not self.started:
            raise RuntimeError("runtime must be started before processing commands")
        try:
            mapping = self.linguistic.map_intent(text)
            accepted = True
            error = ""
        except ValueError as exc:
            mapping = {"intent": "INVALID", "tokens": [], "confidence": 0.0}
            accepted = False
            error = str(exc)
        self.command_count += 1
        payload = {
            "session_id": self.session_id,
            "command_index": self.command_count,
            "raw_length": len(text) if isinstance(text, str) else 0,
            "intent": mapping["intent"],
            "tokens": mapping["tokens"],
            "confidence": mapping["confidence"],
            "accepted": accepted,
            "error": error,
        }
        entry = self.ledger.append("COMMAND", payload)
        envelope = self.signer.sign(payload)
        return {
            "accepted": accepted,
            "intent": mapping["intent"],
            "tokens": mapping["tokens"],
            "confidence": mapping["confidence"],
            "error": error,
            "entry_id": entry.entry_id,
            "entry_hash": entry.entry_hash,
            "signature": envelope.to_dict(),
        }

    def shutdown(self, clean: bool = True) -> Dict[str, Any]:
        self.ledger.append(
            "RUNTIME_SHUTDOWN",
            {"session_id": self.session_id, "clean": bool(clean)},
        )
        state: RestartState = self.restart_manager.save_state(self.ledger, clean=clean)
        receipt = {
            "status": "SHUTDOWN",
            "clean": bool(clean),
            "session_id": self.session_id,
            "last_entry_id": state.last_entry_id,
            "last_entry_hash": state.last_entry_hash,
            "chain_valid": self.ledger.verify_chain(),
            "shutdown_at": _utc_now(),
        }
        self.ledger.close()
        self.started = False
        return receipt

    # -- introspection --------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "version": self.version,
            "started": self.started,
            "commands_processed": self.command_count,
            "linguistic_core": {
                "lexicon_version": self.linguistic.lexicon_version(),
                "status": "UNIT_TESTED",
            },
            "identity": {
                "registered": len(self.identities),
                "status": "UNIT_TESTED",
            },
            "ledger": {
                "path": self.ledger_path,
                "entry_count": self.ledger.count(),
                "head_hash": self.ledger.head_hash(),
                "chain_valid": self.ledger.verify_chain(),
                "status": "LOCALLY_PROVEN",
            },
            "signer": {
                "test_signer": self.signer.trust_level,
                "production_signer": self.production_signer.trust_level,
                "production_configured": self.production_signer.is_configured(),
            },
            "dns": {
                "last_status": self.dns.last_status,
                "status_cap": "LOCALLY_EXECUTED",
                "authoritative_external_confirmed": False,
            },
            "restart": {
                "state_path": self.state_path,
                "status": "RESTART_TESTED",
            },
            "reported_at": _utc_now(),
        }
