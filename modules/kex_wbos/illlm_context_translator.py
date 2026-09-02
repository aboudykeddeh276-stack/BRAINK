#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from capabilities import mint_capability
from hardening import canonical_json_bytes
from illlm_recursive_runtime import RecursiveILLLMRuntime

_ROUTE = re.compile(r"^(?P<action>[A-Z0-9_]+)::(?P<target>.+)$")


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@dataclass(slots=True)
class TranslationContext:
    caller_illlm: str
    global_context: str
    authority: str
    query: str
    requested_role: str | None = None
    require_execution: bool = True
    ttl_seconds: int = 300


class ILLLMContextTranslator:
    """Compile contextual intent into a narrowly scoped KEX capability.

    Security boundary:
    - caller prose/intent is not an actuator command;
    - the global IL-LLM graph resolves a resident execution object;
    - only an explicitly encoded ACTION::TARGET route can be compiled;
    - the emitted capability is limited to that action and target prefix.
    """

    def __init__(self, runtime: RecursiveILLLMRuntime, secret: str | None = None) -> None:
        self.runtime = runtime
        self.secret = secret if secret is not None else os.getenv("KEX_CAPABILITY_SECRET", "")

    @staticmethod
    def _decode_route(route: str) -> tuple[str, str]:
        match = _ROUTE.match(route.strip())
        if not match:
            raise ValueError("execution route must use ACTION::TARGET form")
        action = match.group("action").upper()
        target = match.group("target")
        if not target:
            raise ValueError("execution route target is empty")
        return action, target

    def translate(self, ctx: TranslationContext) -> dict[str, Any]:
        if ctx.caller_illlm not in self.runtime.nodes:
            return self._rejected(ctx, "caller_illlm_not_resident")
        if ctx.global_context not in self.runtime.nodes:
            return self._rejected(ctx, "global_context_not_resident")

        # A local IL-LLM enters through a global context subtree. This is an
        # explicit visibility boundary, not a free whole-graph search.
        plan = self.runtime.compile_context_plan(
            ctx.query,
            role=ctx.requested_role,
            within=ctx.global_context,
            require_execution=ctx.require_execution,
        )
        selected = plan.get("selected")
        if not selected:
            return self._rejected(ctx, "no_contextual_execution_object", plan=plan)

        routes = list(selected.get("executionRoutes") or [])
        if not routes:
            return self._rejected(ctx, "selected_object_has_no_execution_route", plan=plan)

        # Ambiguous executable routes are not silently collapsed. A future
        # equivalence/cost extractor may resolve them, but current compilation
        # must remain deterministic and reviewable.
        decoded: list[tuple[str, str, str]] = []
        for route in routes:
            try:
                action, target = self._decode_route(str(route))
                decoded.append((action, target, str(route)))
            except ValueError:
                continue
        if not decoded:
            return self._rejected(ctx, "no_typed_execution_route", plan=plan)
        decoded.sort(key=lambda item: (item[0], item[1], item[2]))
        action, target, route = decoded[0]

        if not self.secret:
            return self._rejected(
                ctx,
                "capability_secret_not_resident",
                plan=plan,
                typedAction={"action": action, "target": target, "route": route},
            )

        token = mint_capability(
            self.secret,
            actions=[action],
            target_prefixes=[target],
            ttl_seconds=ctx.ttl_seconds,
            delegated_by=ctx.caller_illlm,
        )
        result = {
            "status": "TRANSLATED",
            "callerILLLM": ctx.caller_illlm,
            "globalContext": ctx.global_context,
            "authority": ctx.authority,
            "query": ctx.query,
            "selected": selected,
            "typedAction": {"action": action, "target": target, "route": route},
            "capability": token,
            "runtimeGeneration": self.runtime.generation,
            "graphHash": self.runtime.graph_hash(),
            "translatedAt": time.time(),
            "proofObligations": [
                "execution receipt must identify the same action and target",
                "actuator success must be separately read back",
                "result must re-enter the caller context with proof lineage",
            ],
            "claimBoundary": "This translation authorizes one typed action/target scope. It does not prove actuator execution or external success.",
        }
        unsigned = dict(result)
        unsigned.pop("capability", None)
        result["translationHash"] = _hash(unsigned)
        return result

    def _rejected(self, ctx: TranslationContext, reason: str, **details: Any) -> dict[str, Any]:
        result = {
            "status": "REJECTED",
            "reason": reason,
            "callerILLLM": ctx.caller_illlm,
            "globalContext": ctx.global_context,
            "authority": ctx.authority,
            "query": ctx.query,
            "runtimeGeneration": self.runtime.generation,
            "graphHash": self.runtime.graph_hash(),
            "details": details,
            "translatedAt": time.time(),
        }
        result["translationHash"] = _hash(result)
        return result
