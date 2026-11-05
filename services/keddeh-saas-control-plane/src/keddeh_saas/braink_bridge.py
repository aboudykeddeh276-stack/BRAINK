from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from runtime.illlm_ledger import ILLLMImmutableLedger
from runtime.runtime_registry import RuntimeRegistry

SOURCE_URI = "service://keddeh/saas-control-plane"
SOURCE_LEVEL = "SAAS_CONTROL"
RUNTIME_ID = "runtime://braink/saas-control-plane"
RUNTIME_COMMAND = "uvicorn"
RUNTIME_ARGV = [
    "keddeh_saas.app:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
    "--workers",
    "1",
]


class BrainkBridge:
    """Adapter to resident BRAINK runtime/evidence mechanisms.

    This module does not replace BRAINK authority.  It imports the resident
    implementations from ``runtime/`` and treats them as dependencies.
    Existing runtime records are never overwritten by this adapter.
    """

    def __init__(self, state_dir: str | Path | None = None) -> None:
        default = os.getenv("BRAINK_SAAS_STATE_DIR", "/data/braink")
        self.state_dir = Path(state_dir or default).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ILLLMImmutableLedger(self.state_dir / "illlm-immutable-ledger.jsonl")
        self.registry = RuntimeRegistry(self.state_dir / "runtimes.sqlite")

    def preflight(self) -> dict[str, Any]:
        ledger = self.ledger.verify()
        if ledger.get("status") != "PASS":
            raise RuntimeError(f"BRAINK_ILLLM_LEDGER_INVALID:{ledger}")
        existing = self.registry.get(RUNTIME_ID)
        return {
            "status": "PASS",
            "illlm_ledger": ledger,
            "runtime_record": self.registry.inflate(existing) if existing else None,
            "runtime_record_state": "EXISTING" if existing else "ABSENT",
        }

    def record(self, semantic_type: str, correlation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.preflight()
        event = self.ledger.append(
            source_uri=SOURCE_URI,
            source_level=SOURCE_LEVEL,
            semantic_type=semantic_type,
            correlation_id=correlation_id,
            payload=payload,
            lexical_state={
                "source_uri": SOURCE_URI,
                "source_level": SOURCE_LEVEL,
                "semantic_type": semantic_type,
                "correlation_id": correlation_id,
            },
            illlm_state={
                "semantic_type": semantic_type,
                "correlation_id": correlation_id,
                "payload": payload,
            },
        )
        return asdict(event)

    def admit_runtime_candidate(self) -> dict[str, Any]:
        """Register this service only when the runtime id is currently absent.

        A pre-existing runtime record is returned unchanged.  A conflicting
        record is never rewritten, because a derived service package has no
        authority to replace an established BRAINK runtime definition.
        """
        self.preflight()
        existing = self.registry.get(RUNTIME_ID)
        if existing:
            inflated = self.registry.inflate(existing)
            expected = {
                "command_route": RUNTIME_COMMAND,
                "argv": RUNTIME_ARGV,
            }
            compatible = (
                inflated.get("command_route") == expected["command_route"]
                and inflated.get("argv") == expected["argv"]
            )
            return {
                "status": "PRESERVED_EXISTING",
                "mutated": False,
                "compatible_with_candidate": compatible,
                "runtime": inflated,
            }

        created = self.registry.upsert(
            {
                "runtime_id": RUNTIME_ID,
                "runtime_class": "SERVICE_PROCESS",
                "command_route": RUNTIME_COMMAND,
                "argv": RUNTIME_ARGV,
                "pid": None,
                "health_endpoint": "http://127.0.0.1:8000/health",
                "dependencies": [
                    "runtime://braink/illlm-ledger",
                    "sector://servers-keddeh-systems",
                ],
                "generation": 0,
                "desired_state": "STOPPED",
                "observed_state": "DEFINED",
                "restart_count": 0,
                "last_readback": None,
                "last_failure": None,
            }
        )
        event = self.record(
            "SAAS_RUNTIME_CANDIDATE_REGISTERED",
            RUNTIME_ID,
            {
                "runtime_id": RUNTIME_ID,
                "state_root": created["state_root"],
                "observed_state": created["observed_state"],
                "desired_state": created["desired_state"],
            },
        )
        return {
            "status": "REGISTERED_CANDIDATE",
            "mutated": True,
            "runtime": self.registry.inflate(created),
            "illlm_event_root": event["event_root"],
        }
