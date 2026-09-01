#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from capabilities import mint_capability
from illlm_recursive_runtime import RecursiveILLLMRuntime, _tokens


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


@dataclass(slots=True)
class ContextAuthority:
    context_id: str
    global_frame: str
    local_illlm: str
    allowed_actions: tuple[str, ...]
    target_prefixes: tuple[str, ...]
    expires_at: float
    delegated_by: str

    def allows(self, action: str, target: str) -> bool:
        if time.time() > self.expires_at:
            return False
        if action not in self.allowed_actions:
            return False
        return any(target.startswith(prefix) for prefix in self.target_prefixes)


class ILLLMContextGateway:
    """Interposes global IL-LLM context between local IL-LLM intent and execution.

    A local IL-LLM enters through a global context frame. The frame constrains
    visible targets/actions. Translation emits a typed residual action plus a
    narrowly scoped capability. Execution remains a separate runtime operation.
    """

    def __init__(self, runtime: RecursiveILLLMRuntime, capability_secret: str) -> None:
        if not capability_secret:
            raise ValueError("capability_secret_required")
        self.runtime = runtime
        self.capability_secret = capability_secret
        self.contexts: dict[str, ContextAuthority] = {}

    def open_context(
        self,
        *,
        global_identity: str,
        local_illlm: str,
        allowed_actions: list[str],
        target_prefixes: list[str],
        delegated_by: str,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        if global_identity not in self.runtime.nodes:
            raise KeyError(f"global context not resident: {global_identity}")
        if local_illlm not in self.runtime.nodes:
            raise KeyError(f"local IL-LLM not resident: {local_illlm}")
        if not allowed_actions or not target_prefixes:
            raise ValueError("context_scope_must_be_nonempty")
        global_descendants = self.runtime.descendants(global_identity) | {global_identity}
        if local_illlm not in global_descendants and global_identity != self.runtime.META_ROOT:
            raise ValueError("local_illlm_outside_global_context")
        context_id = f"illlm-context://{uuid.uuid4().hex}"
        frame = self.runtime.enter(local_illlm, entered_from=global_identity)
        authority = ContextAuthority(
            context_id=context_id,
            global_frame=global_identity,
            local_illlm=local_illlm,
            allowed_actions=tuple(sorted(set(allowed_actions))),
            target_prefixes=tuple(sorted(set(target_prefixes))),
            expires_at=time.time() + max(1, ttl_seconds),
            delegated_by=delegated_by,
        )
        self.contexts[context_id] = authority
        body = {
            "contextId": context_id,
            "frameId": frame.frame_id,
            "globalFrame": global_identity,
            "localILLLM": local_illlm,
            "allowedActions": list(authority.allowed_actions),
            "targetPrefixes": list(authority.target_prefixes),
            "expiresAt": authority.expires_at,
            "delegatedBy": delegated_by,
            "state": "OPEN",
        }
        body["contextHash"] = _sha(body)
        return body

    def translate_intent(self, context_id: str, intent: dict[str, Any]) -> dict[str, Any]:
        authority = self.contexts.get(context_id)
        if authority is None:
            raise KeyError("context_not_found")
        action = str(intent.get("actionType", "")).strip()
        target = str(intent.get("target", "")).strip()
        if not action or not target:
            raise ValueError("action_and_target_required")
        if not authority.allows(action, target):
            raise PermissionError("context_authority_denied")

        query = " ".join(
            str(value)
            for value in (
                intent.get("intent"), action, target, intent.get("role"), intent.get("domain")
            )
            if value
        )
        plan = self.runtime.compile_context_plan(
            query,
            within=authority.local_illlm,
            require_execution=False,
        )
        capability = mint_capability(
            self.capability_secret,
            actions=[action],
            target_prefixes=[target],
            ttl_seconds=max(1, int(authority.expires_at - time.time())),
            delegated_by=f"ILLLM_CONTEXT:{context_id}",
        )
        residual = {
            "authority": intent.get("authority"),
            "actionType": action,
            "target": target,
            "payload": intent.get("payload", {}),
            "capability": capability,
            "context": {
                "contextId": context_id,
                "globalFrame": authority.global_frame,
                "localILLLM": authority.local_illlm,
                "selectedSemanticObject": (plan.get("selected") or {}).get("identity"),
                "planHash": plan["planHash"],
            },
            "proofObligations": [
                "typed_intent_translation",
                "capability_scope_match",
                "runtime_receipt",
                "context_reentry",
            ],
        }
        residual["translationHash"] = _sha(residual)
        return {
            "status": "TRANSLATED",
            "contextId": context_id,
            "plan": plan,
            "residualAction": residual,
            "claimBoundary": "Translation proves scoped intent-to-action compilation. It does not prove the downstream action executed.",
        }

    def reenter(self, context_id: str, *, receipt: dict[str, Any]) -> dict[str, Any]:
        authority = self.contexts.get(context_id)
        if authority is None:
            raise KeyError("context_not_found")
        result = {
            "contextId": context_id,
            "globalFrame": authority.global_frame,
            "localILLLM": authority.local_illlm,
            "receiptHash": receipt.get("receiptHash") or _sha(receipt),
            "receiptStatus": receipt.get("status"),
            "mutated": receipt.get("mutated"),
            "state": "REENTERED",
            "reenteredAt": time.time(),
        }
        result["reentryHash"] = _sha(result)
        return result
