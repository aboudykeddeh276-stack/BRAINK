"""Native BRAINK V4 observer/mirror transport; no host-executor identity is issued.

Architecture: Architect A. Keddeh / KS-BRAINK-IL-LLM.
This is a resident add-on to existing Observer² and IL-LLM ledger mechanisms.
It does not reimplement polygon learning, cluster consensus or generation weights.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from aiohttp import WSMsgType, web
from runtime.illlm_ledger import ILLLMImmutableLedger
from observer2_runtime.kernel import CandidateState, LearningAdmissionGate, SignalPacket

MAX_JSON_BYTES = 131072
MAX_HISTORY_TAIL = 20
TRANSPORT_SCHEMA = "KS-BRAINK-IL-LLM/observer-v4-mirror-transport/1"
LOCAL_CAPABILITY = "BRAINK_V4_LEARNING_MIRROR"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def as_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label}_NOT_OBJECT")
    return value


def bounded_number(value: Any, name: str, maximum: int) -> int:
    if type(value) is not int or not (0 <= value <= maximum):
        raise ValueError(f"INVALID_{name}")
    return value


@dataclass
class BrowserSession:
    session_id: str
    instance_id: str
    last_seen: float
    sequence: int = 0


class V4HostBridge:
    def __init__(self, *, token: str, ledger_path: str | Path,
                 source_path: str | Path, allowed_origins: set[str], heartbeat_ttl: float = 30.0):
        if len(token) < 32:
            raise ValueError("BRAINK_V4_BRIDGE_TOKEN must contain at least 32 characters")
        if not allowed_origins:
            raise ValueError("Explicit origin allowlist required")
        if heartbeat_ttl <= 0:
            raise ValueError("heartbeat TTL must be positive")
        self.token = token
        self.ledger = ILLLMImmutableLedger(ledger_path)
        self.source_path = Path(source_path).resolve()
        self.source_sha256 = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
        self.allowed_origins = allowed_origins
        self.heartbeat_ttl = heartbeat_ttl
        self.sessions: dict[Any, BrowserSession] = {}
        self.app = web.Application(client_max_size=MAX_JSON_BYTES)
        self.app.router.add_get("/", self.page)
        self.app.router.add_get("/v4", self.page)
        self.app.router.add_get("/api/health", self.health)
        self.app.router.add_get("/api/readback", self.readback)
        self.app.router.add_get("/api/ws/state", self.websocket)
        self.app.on_startup.append(self._start_watch)
        self.app.on_cleanup.append(self._stop_watch)

    async def page(self, request: web.Request) -> web.StreamResponse:
        path = self.source_path.with_name("KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4_HOST_LINK.html")
        response = web.FileResponse(path)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    async def health(self, request: web.Request) -> web.Response:
        ledger_status = self.ledger.verify()
        return web.json_response({
            "schema": TRANSPORT_SCHEMA, "status": "BRIDGE_READY" if ledger_status["status"] == "PASS" else "LEDGER_FAILED",
            "browser_learning_sessions": len(self.sessions),
            "external_host_executors": None,  # separate KEDDEH broker's authoritative count
            "learning_promotion": "DISABLED_CANDIDATE_ONLY",
            "ledger": ledger_status, "source_sha256": self.source_sha256,
        })

    async def readback(self, request: web.Request) -> web.Response:
        authorization = request.headers.get("Authorization", "")
        expected = "Bearer " + self.token
        if not hmac.compare_digest(authorization, expected):
            raise web.HTTPUnauthorized()
        correlation_id = request.query.get("correlation_id", "")
        if len(correlation_id) != 64 or not all(c in "0123456789abcdef" for c in correlation_id):
            raise web.HTTPBadRequest(text="correlation_id must be a sha256 hex digest")
        verified = self.ledger.verify()
        if verified["status"] != "PASS":
            raise web.HTTPConflict(text="ledger not verified")
        return web.json_response({"verification": verified,
                                  "events": self.ledger.read_by_correlation(correlation_id)})

    async def _start_watch(self, app: web.Application) -> None:
        self.watch_task = asyncio.create_task(self._expire_sessions())

    async def _stop_watch(self, app: web.Application) -> None:
        self.watch_task.cancel()
        try:
            await self.watch_task
        except asyncio.CancelledError:
            pass
        for ws in list(self.sessions):
            await ws.close()
        self.sessions.clear()

    async def _expire_sessions(self) -> None:
        while True:
            await asyncio.sleep(min(5.0, self.heartbeat_ttl / 2))
            now = time.monotonic()
            for ws, session in list(self.sessions.items()):
                if now - session.last_seen > self.heartbeat_ttl:
                    await ws.close(code=1008, message=b"STALE_HEARTBEAT")
                    self.sessions.pop(ws, None)

    def _validate_mirror(self, payload: Mapping[str, Any], session: BrowserSession):
        if payload.get("schema") != TRANSPORT_SCHEMA:
            raise ValueError("SCHEMA_MISMATCH")
        if payload.get("source_sha256") != self.source_sha256:
            raise ValueError("SOURCE_PROVENANCE_MISMATCH")
        sequence = bounded_number(payload.get("sequence"), "SEQUENCE", 2_147_483_647)
        if sequence <= session.sequence:
            raise ValueError("NON_MONOTONIC_SEQUENCE")
        frame = as_object(payload.get("observer"), "OBSERVER")
        polygon = as_object(payload.get("polygon"), "POLYGON")
        v4_receipt = as_object(payload.get("v4_receipt"), "V4_RECEIPT")
        if frame.get("wholeIdentity") != "1_BRAINK" or frame.get("stateFormula") != "O_AS_OBS=1_O⊗S_O(E)":
            raise ValueError("OBSERVER_SOURCE_FORMULA_MISMATCH")
        if not isinstance(frame.get("queryRoot"), str) or not (1 <= len(frame["queryRoot"]) <= 128):
            raise ValueError("MISSING_QUERY_ROOT")
        if not isinstance(polygon.get("lastSuccessor"), (str, type(None))):
            raise ValueError("INVALID_SUCCESSOR")
        bounded_number(polygon.get("iteration"), "ITERATION", 2_147_483_647)
        history = polygon.get("history_tail")
        if not isinstance(history, list) or len(history) > MAX_HISTORY_TAIL:
            raise ValueError("INVALID_HISTORY_TAIL")
        if any(not isinstance(z, dict) for z in history):
            raise ValueError("INVALID_HISTORY_ENTRY")
        if not isinstance(v4_receipt.get("id"), str) or not (1 <= len(v4_receipt["id"]) <= 200):
            raise ValueError("INVALID_RECEIPT_ID")
        if v4_receipt.get("status") not in {"PASS", "WARN", "FAIL", "BLOCKED"}:
            raise ValueError("INVALID_V4_STATUS")
        candidate_state = {"observer": frame, "polygon": polygon, "v4_receipt": v4_receipt,
                           "source_sha256": self.source_sha256, "instance_id": session.instance_id}
        candidate_hash = digest(candidate_state)
        candidate = CandidateState(candidate_hash, candidate_state, digest(frame), True)
        signal = SignalPacket.build("BRAINK_V4_BROWSER_PROJECTION", LOCAL_CAPABILITY,
                                    "POLYGON_MIRROR_CANDIDATE", {"sequence": sequence}, sequence)
        # Retain Observer²'s implemented admission contract. An *actual* local
        # ledger writer is the actuator, never an invented host executor.
        decision = LearningAdmissionGate().evaluate(signal, candidate,
                                                     {LOCAL_CAPABILITY: {"actuator": self.ledger.append}})
        if not decision.admitted:
            raise ValueError(f"OBSERVER_ADMISSION_DENIED:{decision.reason}")
        return sequence, candidate_hash, candidate_state, decision.policy_digest

    def _record(self, payload: dict[str, Any], session: BrowserSession) -> dict[str, Any]:
        if self.ledger.verify().get("status") != "PASS":
            raise ValueError("CORRUPT_LEDGER")
        sequence, candidate_hash, state, policy_hash = self._validate_mirror(payload, session)
        correlation = digest({"instance_id": session.instance_id,
                              "v4_receipt_id": state["v4_receipt"]["id"],
                              "source_sha256": self.source_sha256})
        prior = self.ledger.read_by_correlation(correlation)
        if prior:
            if len(prior) != 1:
                raise ValueError("DUPLICATE_CORRELATION_REQUIRES_RECONCILIATION")
            if prior[0].get("payload", {}).get("candidate_hash") != candidate_hash:
                raise ValueError("CANDIDATE_REPLAY_CONFLICT")
            event = prior[0]
        else:
            appended = self.ledger.append(
                source_uri=f"braink://learning/v4/browser/{session.instance_id}",
                source_level="OBSERVER_MIRROR_ONLY",
                semantic_type="POLYGON_MIRROR_CANDIDATE",
                correlation_id=correlation,
                payload={"candidate_hash": candidate_hash, "sequence": sequence,
                         "observer_policy_digest": policy_hash, "state": state,
                         "promotion_state": "NOT_PROMOTED"},
                lexical_state={"source": "V4", "receipt": state["v4_receipt"],
                               "polygon_lexical_context": state["polygon"]},
                illlm_state={"candidate": candidate_hash, "observer": state["observer"],
                             "source": self.source_sha256, "authority": "MIRROR_ONLY"},
                idempotency_payload_field="candidate_hash",
            )
            event = asdict(appended)
        session.sequence = sequence
        return {"action": "MIRROR_COMMITTED", "correlation_id": correlation,
                "event_root": event["event_root"], "event_id": event["event_id"],
                "ledger_head": self.ledger.head(), "promotion_state": "NOT_PROMOTED",
                "sequence": sequence}

    async def websocket(self, request: web.Request) -> web.StreamResponse:
        if request.headers.get("Origin", "") not in self.allowed_origins:
            raise web.HTTPForbidden(text="ORIGIN_NOT_ALLOWED")
        ws = web.WebSocketResponse(max_msg_size=MAX_JSON_BYTES, autoping=True, heartbeat=15)
        await ws.prepare(request)
        session: BrowserSession | None = None
        try:
            async for incoming in ws:
                if incoming.type != WSMsgType.TEXT:
                    if incoming.type == WSMsgType.ERROR:
                        break
                    continue
                try:
                    if len(incoming.data.encode("utf-8")) > MAX_JSON_BYTES:
                        raise ValueError("FRAME_TOO_LARGE")
                    payload = as_object(json.loads(incoming.data), "PAYLOAD")
                    action = payload.get("action")
                    if not session:
                        if action != "AUTH" or not isinstance(payload.get("token"), str) or not hmac.compare_digest(payload["token"], self.token):
                            await ws.send_json({"action": "REJECTED", "reason": "AUTH_REQUIRED"})
                            await ws.close(code=1008, message=b"AUTH_REQUIRED")
                            break
                        instance_id = payload.get("instance_id", "")
                        if not isinstance(instance_id, str) or not (8 <= len(instance_id) <= 128) or not all(ch.isalnum() or ch in "-_:" for ch in instance_id):
                            raise ValueError("INVALID_INSTANCE_ID")
                        session = BrowserSession(secrets.token_hex(16), instance_id, time.monotonic())
                        self.sessions[ws] = session
                        await ws.send_json({"action": "AUTH_ACCEPTED", "session_id": session.session_id,
                                            "source_sha256": self.source_sha256, "scope": "BROWSER_LEARNING_MIRROR_ONLY"})
                        continue
                    session.last_seen = time.monotonic()
                    if action == "HEARTBEAT":
                        await ws.send_json({"action": "HEARTBEAT_ACK", "session_id": session.session_id})
                    elif action == "STATE_TELEMETRY":
                        receipt = self._record(payload, session)
                        await ws.send_json(receipt)
                    else:
                        raise ValueError("UNSUPPORTED_ACTION")
                except (json.JSONDecodeError, ValueError, TypeError, OverflowError) as exc:
                    await ws.send_json({"action": "REJECTED", "reason": str(exc)[:200]})
        finally:
            self.sessions.pop(ws, None)
        return ws


def main() -> None:
    port = int(os.environ.get("BRAINK_V4_BRIDGE_PORT", "8080"))
    bind = os.environ.get("BRAINK_V4_BRIDGE_BIND", "127.0.0.1")
    token = os.environ.get("BRAINK_V4_BRIDGE_TOKEN", "")
    origin_default = f"http://127.0.0.1:{port},http://localhost:{port}"
    origins = set(filter(None, (x.strip() for x in os.environ.get("BRAINK_V4_ALLOWED_ORIGINS", origin_default).split(","))))
    source_path = Path(__file__).resolve().with_name("KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html")
    ledger_path = Path(os.environ.get("BRAINK_V4_LEDGER_PATH", ".kex/state/illlm-v4-mirror.jsonl"))
    bridge = V4HostBridge(token=token, ledger_path=ledger_path, source_path=source_path, allowed_origins=origins)
    web.run_app(bridge.app, host=bind, port=port, access_log=None)


if __name__ == "__main__":
    main()
