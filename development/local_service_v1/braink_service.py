from __future__ import annotations

import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuthorizationError(PermissionError):
    pass


class EvidenceLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, transaction_id: str, action: str, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "transaction_id": transaction_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def trace(self, transaction_id: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            event
            for event in (json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines())
            if event["transaction_id"] == transaction_id
        ]


class BRAINKService:
    """Smallest proof-bearing conversation -> skill -> tool -> evidence loop."""

    ALLOWED_TOOLS = {"runtime.identity"}

    def __init__(self, ledger_path: Path | str):
        self.ledger = EvidenceLedger(Path(ledger_path))

    def respond(self, request: dict[str, Any]) -> dict[str, Any]:
        message = request.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")

        tx = str(uuid.uuid4())
        self.ledger.append(tx, "request_received", {"message": message})

        context = {"message": message.strip(), "mode": "local", "evidence_required": True}
        self.ledger.append(tx, "context_resolved", context)

        skill = self._select_skill(context)
        tool = request.get("requested_tool") or "runtime.identity"
        self.ledger.append(tx, "skill_selected", {"skill": skill, "tool": tool})

        authorized = tool in self.ALLOWED_TOOLS
        self.ledger.append(tx, "authorization_decision", {"tool": tool, "authorized": authorized})
        if not authorized:
            raise AuthorizationError(f"tool not authorized: {tool}")

        self.ledger.append(tx, "tool_started", {"tool": tool})
        try:
            result = self._invoke_tool(tool)
        except Exception as exc:
            self.ledger.append(tx, "tool_failure", {"tool": tool, "error": str(exc)})
            raise
        self.ledger.append(tx, "tool_result", {"tool": tool, "result": result})

        response_text = self._continue_inference(context, skill, result)
        self.ledger.append(tx, "inference_resumed", {"skill": skill, "tool_evidence": result})

        response = {
            "transaction_id": tx,
            "status": "ok",
            "skill": skill,
            "tool": tool,
            "response": response_text,
        }
        self.ledger.append(tx, "response_emitted", response)
        return response

    def trace(self, transaction_id: str) -> list[dict[str, Any]]:
        return self.ledger.trace(transaction_id)

    @staticmethod
    def _select_skill(context: dict[str, Any]) -> str:
        message = context["message"].lower()
        if any(token in message for token in ("runtime", "diagnose", "service", "system")):
            return "runtime_diagnostic"
        return "conversation_core"

    @staticmethod
    def _invoke_tool(tool: str) -> dict[str, Any]:
        if tool != "runtime.identity":
            raise AuthorizationError(f"no implementation for tool: {tool}")
        return {
            "runtime": "BRAINK-local-service-v1",
            "python": platform.python_version(),
            "platform": platform.system(),
        }

    @staticmethod
    def _continue_inference(context: dict[str, Any], skill: str, evidence: dict[str, Any]) -> str:
        # V1 uses deterministic continuation so the evidence handoff is directly testable.
        # A local model adapter can replace this boundary without changing the orchestration contract.
        return (
            f"{skill}: observed {evidence['runtime']} on {evidence['platform']} "
            f"with Python {evidence['python']} for request: {context['message']}"
        )
