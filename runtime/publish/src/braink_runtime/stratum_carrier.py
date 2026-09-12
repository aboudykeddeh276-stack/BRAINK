from __future__ import annotations

import asyncio
import json
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StratumEndpoint:
    name: str
    host: str
    port: int
    tls: bool = False
    purpose: str = "BTC"


VIABTC_ENDPOINTS: dict[str, StratumEndpoint] = {
    "BTC_PRIMARY": StratumEndpoint("BTC_PRIMARY", "btc.viabtc.io", 3333, False, "BTC"),
    "BTC_FAILOVER": StratumEndpoint("BTC_FAILOVER", "btc.viabtc.io", 443, False, "BTC"),
    "BTC_SSL": StratumEndpoint("BTC_SSL", "btc-ssl.viabtc.io", 551, True, "BTC"),
    "SMART_PRIMARY": StratumEndpoint("SMART_PRIMARY", "bitcoin.viabtc.io", 3333, False, "SMART_MINING"),
    "SMART_FAILOVER": StratumEndpoint("SMART_FAILOVER", "bitcoin.viabtc.io", 443, False, "SMART_MINING"),
}


class StratumProtocolError(RuntimeError):
    pass


async def _read_json_line(reader: asyncio.StreamReader, timeout_s: float) -> dict[str, Any]:
    raw = await asyncio.wait_for(reader.readline(), timeout=timeout_s)
    if not raw:
        raise ConnectionResetError("STRATUM_EOF")
    try:
        message = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise StratumProtocolError("STRATUM_INVALID_JSON") from exc
    if not isinstance(message, dict):
        raise StratumProtocolError("STRATUM_MESSAGE_NOT_OBJECT")
    return message


async def probe_stratum(
    endpoint: StratumEndpoint,
    *,
    worker_name: str | None = None,
    password: str = "x",
    timeout_s: float = 4.0,
    observe_s: float = 2.0,
    user_agent: str = "BRAINK-KEX/1.0",
) -> dict[str, Any]:
    """Establish a read-only Stratum session and return a typed receipt.

    The probe sends mining.subscribe and may send mining.authorize when a worker
    name is explicitly configured. It never sends mining.submit.
    """
    started_ns = time.time_ns()
    ssl_ctx = ssl.create_default_context() if endpoint.tls else None
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(endpoint.host, endpoint.port, ssl=ssl_ctx, server_hostname=endpoint.host if endpoint.tls else None),
        timeout=timeout_s,
    )
    sock = writer.get_extra_info("socket")
    if sock is not None:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    events: list[dict[str, Any]] = []
    subscribe_id = 1
    subscribe = {"id": subscribe_id, "method": "mining.subscribe", "params": [user_agent]}
    writer.write((json.dumps(subscribe, separators=(",", ":")) + "\n").encode("utf-8"))
    await writer.drain()

    subscription_result: Any = None
    authorized: bool | None = None
    extranonce1: str | None = None
    extranonce2_size: int | None = None
    difficulty: float | None = None
    current_job_id: str | None = None

    try:
        first = await _read_json_line(reader, timeout_s)
        events.append(first)
        if first.get("id") != subscribe_id:
            raise StratumProtocolError("STRATUM_SUBSCRIBE_RESPONSE_ID_MISMATCH")
        if first.get("error") not in (None, False):
            raise StratumProtocolError(f"STRATUM_SUBSCRIBE_ERROR:{first.get('error')}")
        subscription_result = first.get("result")
        if isinstance(subscription_result, list) and len(subscription_result) >= 3:
            extranonce1 = str(subscription_result[1]) if subscription_result[1] is not None else None
            try:
                extranonce2_size = int(subscription_result[2])
            except (TypeError, ValueError):
                extranonce2_size = None

        if worker_name:
            authorize_id = 2
            authorize = {"id": authorize_id, "method": "mining.authorize", "params": [worker_name, password]}
            writer.write((json.dumps(authorize, separators=(",", ":")) + "\n").encode("utf-8"))
            await writer.drain()

        deadline = asyncio.get_running_loop().time() + max(0.0, observe_s)
        while asyncio.get_running_loop().time() < deadline:
            remaining = min(timeout_s, max(0.01, deadline - asyncio.get_running_loop().time()))
            try:
                msg = await _read_json_line(reader, remaining)
            except asyncio.TimeoutError:
                break
            events.append(msg)
            if worker_name and msg.get("id") == 2:
                authorized = bool(msg.get("result")) and msg.get("error") in (None, False)
            method = msg.get("method")
            params = msg.get("params") or []
            if method == "mining.set_difficulty" and params:
                try:
                    difficulty = float(params[0])
                except (TypeError, ValueError):
                    pass
            elif method == "mining.notify" and params:
                current_job_id = str(params[0])
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    return {
        "schema": "braink.kex.stratum.session-receipt.v1",
        "status": "SESSION_ESTABLISHED",
        "endpoint": asdict(endpoint),
        "transport": "TLS" if endpoint.tls else "TCP",
        "socket_flags": ["TCP_NODELAY", "SO_KEEPALIVE"],
        "subscription_result_present": subscription_result is not None,
        "authorized": authorized,
        "worker_name": worker_name,
        "extranonce1": extranonce1,
        "extranonce2_size": extranonce2_size,
        "difficulty": difficulty,
        "current_job_id": current_job_id,
        "messages_observed": len(events),
        "methods_observed": sorted({str(e.get("method")) for e in events if e.get("method")}),
        "share_submission": "NOT_PERFORMED",
        "accepted_shares": "NOT_DERIVED_FROM_PROBE",
        "bitcoin_block_discovery": False,
        "started_ns": started_ns,
        "completed_ns": time.time_ns(),
    }
