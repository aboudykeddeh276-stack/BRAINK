#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from hardening import constant_time_bearer_matches, contained_path, require_secure_bind
from illlm_context_translator import ILLLMContextTranslator, TranslationContext
from illlm_delta_engine import DeltaEngine, Fact, default_kex_rules
from illlm_equivalence import EquivalenceStore, EquivalentForm
from illlm_higher_order import build_topology
from illlm_hydrator import apply_delta, hydrate_recursive_runtime
from workbook_illlm_bridge import hydrate_workbook_into_illlm

BASE = Path(__file__).resolve().parents[2]
WORKBOOK_ROOTS = (
    BASE / "workbooks",
    BASE / "runtime" / "workbooks",
)


class RuntimeHolder:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.runtime = hydrate_recursive_runtime(build_topology())
        self.delta_engine = DeltaEngine()
        for rule in default_kex_rules():
            self.delta_engine.add_rule(rule)
        self.equivalence = EquivalenceStore()
        self.loaded_at = time.time()
        self.last_delta: dict[str, Any] | None = None
        self.last_fact_delta: dict[str, Any] | None = None
        self.last_workbook_hydration: dict[str, Any] | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            snap = self.runtime.snapshot()
            snap.update({
                "loadedAt": self.loaded_at,
                "lastGraphDelta": self.last_delta,
                "lastWorkbookHydration": self.last_workbook_hydration,
                "factEngine": {
                    "generation": self.delta_engine.generation,
                    "residentFactCount": len(self.delta_engine.facts),
                    "graphHash": self.delta_engine.graph_hash(),
                    "lastDelta": self.last_fact_delta,
                    "totalRuleEvaluations": self.delta_engine.total_rule_evaluations,
                },
                "equivalenceClassCount": len(self.equivalence.classes),
            })
            return snap

    def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.runtime.compile_context_plan(
                str(payload.get("query", "")),
                role=payload.get("role"),
                within=payload.get("within"),
                require_execution=bool(payload.get("requireExecution", False)),
            )

    def traverse(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.runtime.shortest_traversal(
                str(payload["source"]),
                str(payload["target"]),
                executable_only=bool(payload.get("executableOnly", False)),
            )

    def translate(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            translator = ILLLMContextTranslator(self.runtime)
            context = TranslationContext(
                caller_illlm=str(payload["callerILLLM"]),
                global_context=str(payload["globalContext"]),
                authority=str(payload.get("authority", "")),
                query=str(payload.get("query", "")),
                requested_role=str(payload["role"]) if payload.get("role") is not None else None,
                require_execution=bool(payload.get("requireExecution", True)),
                ttl_seconds=int(payload.get("ttlSeconds", 300)),
            )
            return translator.translate(context)

    def graph_delta(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            result = apply_delta(self.runtime, payload)
            self.last_delta = {"at": time.time(), **result}
            return result

    def fact_delta(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get("facts", [])
        facts: list[Fact] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("each fact must be an object")
            facts.append(Fact(str(item["predicate"]), str(item["subject"]), str(item["object"])))
        with self.lock:
            result = self.delta_engine.insert(facts)
            self.last_fact_delta = {"at": time.time(), **result}
            return result

    def fact_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            rows = self.delta_engine.query(
                str(payload["predicate"]),
                subject=str(payload["subject"]) if payload.get("subject") is not None else None,
                object=str(payload["object"]) if payload.get("object") is not None else None,
            )
            return {
                "status": "RESIDENT",
                "rows": [
                    {"predicate": row.predicate, "subject": row.subject, "object": row.object}
                    for row in rows
                ],
                "count": len(rows),
                "generation": self.delta_engine.generation,
                "graphHash": self.delta_engine.graph_hash(),
            }

    def equivalence_register(self, payload: dict[str, Any]) -> dict[str, Any]:
        form = EquivalentForm(
            identity=str(payload["identity"]),
            form=str(payload["form"]),
            cost=float(payload.get("cost", 1.0)),
            proof_status=str(payload.get("proofStatus", "DEFINED")),
            executable_route=str(payload["executableRoute"]) if payload.get("executableRoute") else None,
        )
        with self.lock:
            self.equivalence.register(str(payload["classId"]), form)
            return {"status": "REGISTERED", "classId": str(payload["classId"]), "identity": form.identity}

    def equivalence_extract(self, payload: dict[str, Any]) -> dict[str, Any]:
        statuses = payload.get("allowedProofStatus")
        allowed = {str(item) for item in statuses} if isinstance(statuses, list) else None
        with self.lock:
            return self.equivalence.extract(
                str(payload["classId"]),
                require_execution=bool(payload.get("requireExecution", False)),
                allowed_proof_status=allowed,
            )

    def _resolve_workbook_path(self, raw: str) -> Path:
        supplied = Path(raw)
        candidates: list[Path] = []
        if supplied.is_absolute():
            candidates.append(supplied)
        else:
            candidates.extend(root / supplied for root in WORKBOOK_ROOTS)
        for candidate in candidates:
            for root in WORKBOOK_ROOTS:
                try:
                    resolved = contained_path(root, candidate)
                except ValueError:
                    continue
                if resolved.is_file() and resolved.suffix.lower() in {".xlsx", ".xlsm"}:
                    return resolved
        raise ValueError("workbook_not_found_or_outside_allowed_roots")

    def workbook_hydrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        workbook = self._resolve_workbook_path(str(payload["path"]))
        raw_routes = payload.get("executionRoutes", {})
        if raw_routes is None:
            raw_routes = {}
        if not isinstance(raw_routes, dict):
            raise ValueError("executionRoutes_must_be_object")
        routes: dict[str, tuple[str, ...]] = {}
        for object_id, values in raw_routes.items():
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError("executionRoutes_values_must_be_string_arrays")
            routes[str(object_id)] = tuple(values)
        with self.lock:
            receipt = hydrate_workbook_into_illlm(self.runtime, workbook, execution_routes=routes)
            self.last_workbook_hydration = {"at": time.time(), **receipt}
            return receipt

    def rebuild(self) -> dict[str, Any]:
        with self.lock:
            previous = self.runtime.graph_hash()
            self.runtime = hydrate_recursive_runtime(build_topology())
            self.loaded_at = time.time()
            self.last_workbook_hydration = None
            return {
                "status": "REBUILT",
                "previousGraphHash": previous,
                "graphHash": self.runtime.graph_hash(),
                "nodeCount": len(self.runtime.nodes),
                "generation": self.runtime.generation,
                "claimBoundary": "Full rebuild is a recovery/reindex operation. Warm fact/equivalence/workbook state is intentionally separate and is not silently fabricated from the rebuilt topology.",
            }


HOLDER = RuntimeHolder()


class Handler(BaseHTTPRequestHandler):
    server_version = "KEX-ILLLM/2.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _auth_ok(self) -> bool:
        expected = os.getenv("KEX_BEARER_TOKEN", "")
        if not expected:
            return True
        return constant_time_bearer_matches(self.headers.get("Authorization"), expected)

    def _json(self, status: int, body: Any) -> None:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > int(os.getenv("KEX_ILLLM_MAX_REQUEST_BYTES", "1048576")):
            raise ValueError("request_too_large")
        raw = self.rfile.read(length) if length else b"{}"
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("object_required")
        return value

    def do_GET(self) -> None:
        if self.path in {"/health", "/snapshot"}:
            if not self._auth_ok():
                self._json(401, {"status": "UNAUTHORIZED"}); return
            snap = HOLDER.snapshot()
            self._json(200, {"status": "ok", "service": "service://illlm/recursive-runtime", **snap})
            return
        self._json(404, {"status": "NOT_FOUND"})

    def do_POST(self) -> None:
        if not self._auth_ok():
            self._json(401, {"status": "UNAUTHORIZED"}); return
        try:
            payload = self._body()
            handlers = {
                "/query": HOLDER.query,
                "/traverse": HOLDER.traverse,
                "/translate": HOLDER.translate,
                "/delta": HOLDER.graph_delta,
                "/facts/delta": HOLDER.fact_delta,
                "/facts/query": HOLDER.fact_query,
                "/equivalence/register": HOLDER.equivalence_register,
                "/equivalence/extract": HOLDER.equivalence_extract,
                "/workbooks/hydrate": HOLDER.workbook_hydrate,
            }
            handler = handlers.get(self.path)
            if handler:
                self._json(200, handler(payload)); return
            if self.path == "/rebuild":
                self._json(200, HOLDER.rebuild()); return
            self._json(404, {"status": "NOT_FOUND"})
        except (KeyError, ValueError, RuntimeError) as exc:
            self._json(400, {"status": "REJECTED", "error": type(exc).__name__, "message": str(exc)})
        except Exception as exc:
            self._json(500, {"status": "FAIL", "error": type(exc).__name__})


def serve(host: str = "127.0.0.1", port: int = 8791) -> None:
    require_secure_bind(host, os.getenv("KEX_BEARER_TOKEN"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("KEX_ILLLM_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("KEX_ILLLM_PORT", "8791")))
    args = parser.parse_args()
    serve(args.host, args.port)
