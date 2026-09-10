#!/usr/bin/env python3
"""BRAINK/KEX ViaBTC blade01 execution-closure actuator.

Purpose
-------
Open the configured ViaBTC Smart Mining Stratum V1 channel, subscribe,
authorize ``<account>.blade01``, receive fresh jobs, hand each proven job to a
resident hasher adapter over JSON-lines stdin/stdout, submit any returned
candidate on the SAME origin Stratum stream, and emit JSON receipts suitable
for workbook reconciliation.

No candidate is promoted to ACCEPTED without the correlated upstream
``mining.submit`` response.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import socket
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

SMART_HOST = os.getenv("KEX_VIABTC_HOST", "bitcoin.viabtc.io")
SMART_PORT = int(os.getenv("KEX_VIABTC_PORT", "3333"))
ACCOUNT = os.getenv("KEX_VIABTC_ACCOUNT", "keddeh")
WORKER_SUFFIX = os.getenv("KEX_VIABTC_WORKER", "blade01")
PASSWORD = os.getenv("KEX_VIABTC_PASSWORD", "x")
HASHER_ADAPTER = os.getenv("KEX_HASHER_ADAPTER", "").strip()
TLS = os.getenv("KEX_VIABTC_TLS", "0") == "1"
SOCKET_TIMEOUT = float(os.getenv("KEX_VIABTC_TIMEOUT", "30"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_root(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def emit(event: str, **fields: Any) -> None:
    record = {"timestamp_utc": utc_now(), "event": event, **fields}
    record["receipt_root"] = canonical_root(record)
    print(json.dumps(record, separators=(",", ":"), ensure_ascii=False), flush=True)


@dataclass
class StratumChannel:
    sock: socket.socket
    stream: Any
    worker: str
    route_id: str
    request_id: int = 0
    extranonce1: str = ""
    extranonce2_size: int = 0
    difficulty: float = 0.0
    current_job_id: str = ""

    def next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def send(self, method: str, params: list[Any]) -> int:
        rpc_id = self.next_id()
        payload = {"id": rpc_id, "method": method, "params": params}
        self.stream.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        self.stream.flush()
        emit("STRATUM_TX", rpc_id=rpc_id, method=method, route_id=self.route_id, worker=self.worker)
        return rpc_id

    def read_message(self) -> Dict[str, Any]:
        line = self.stream.readline()
        if not line:
            raise RuntimeError("POOL_EOF")
        msg = json.loads(line.decode(errors="strict"))
        emit("STRATUM_RX", route_id=self.route_id, worker=self.worker, payload_root=canonical_root(msg))
        return msg

    def wait_response(self, rpc_id: int) -> Dict[str, Any]:
        while True:
            msg = self.read_message()
            if msg.get("id") == rpc_id:
                return msg
            self.handle_async(msg)

    def handle_async(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = msg.get("method")
        params = msg.get("params") or []
        if method == "mining.set_difficulty" and params:
            self.difficulty = float(params[0])
            emit("DIFFICULTY", difficulty=self.difficulty, route_id=self.route_id)
        elif method == "mining.set_extranonce" and len(params) >= 2:
            self.extranonce1 = str(params[0])
            self.extranonce2_size = int(params[1])
            emit("EXTRANONCE", extranonce1=self.extranonce1, extranonce2_size=self.extranonce2_size)
        elif method == "mining.notify":
            return self.normalize_job(params)
        return None

    def normalize_job(self, params: list[Any]) -> Dict[str, Any]:
        if len(params) < 9:
            raise ValueError("MALFORMED_NOTIFY")
        job = {
            "route_id": self.route_id,
            "worker": self.worker,
            "job_id": str(params[0]),
            "prevhash": str(params[1]),
            "coinb1": str(params[2]),
            "coinb2": str(params[3]),
            "merkle_branch": list(params[4]),
            "version": str(params[5]),
            "nbits": str(params[6]),
            "ntime": str(params[7]),
            "clean_jobs": bool(params[8]),
            "extranonce1": self.extranonce1,
            "extranonce2_size": self.extranonce2_size,
            "difficulty": self.difficulty,
            "issued_by": "viabtc_blade01_closure",
            "received_utc": utc_now(),
        }
        job["job_key"] = f"{job['route_id']}|{job['job_id']}|{job['ntime']}"
        job["proof_root"] = canonical_root(job)
        self.current_job_id = job["job_id"]
        emit("JOB_BOUND", job_id=job["job_id"], job_key=job["job_key"], job_proof_root=job["proof_root"], clean_jobs=job["clean_jobs"])
        return job


def open_channel() -> StratumChannel:
    raw = socket.create_connection((SMART_HOST, SMART_PORT), timeout=SOCKET_TIMEOUT)
    raw.settimeout(SOCKET_TIMEOUT)
    raw.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock: socket.socket = raw
    if TLS:
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=SMART_HOST)
    stream = sock.makefile("rwb", buffering=0)
    route_id = "ROUTE-VIA-SMART-443" if SMART_PORT == 443 else "ROUTE-VIA-SMART-3333"
    channel = StratumChannel(sock=sock, stream=stream, worker=f"{ACCOUNT}.{WORKER_SUFFIX}", route_id=route_id)

    emit("SOCKET_CONNECTED", host=SMART_HOST, port=SMART_PORT, tls=TLS, route_id=route_id, worker=channel.worker)

    sub_id = channel.send("mining.subscribe", ["KEX/R12"])
    sub = channel.wait_response(sub_id)
    if sub.get("error") or not sub.get("result") or len(sub["result"]) < 3:
        raise RuntimeError(f"SUBSCRIBE_REJECTED:{sub}")
    channel.extranonce1 = str(sub["result"][1])
    channel.extranonce2_size = int(sub["result"][2])
    emit("SUBSCRIBED", extranonce1=channel.extranonce1, extranonce2_size=channel.extranonce2_size, route_id=route_id)

    auth_id = channel.send("mining.authorize", [channel.worker, PASSWORD])
    auth = channel.wait_response(auth_id)
    if auth.get("error") or auth.get("result") is not True:
        raise RuntimeError(f"AUTHORIZE_REJECTED:{auth}")
    emit("AUTHORIZED", route_id=route_id, worker=channel.worker)
    return channel


def dispatch_to_hasher(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not HASHER_ADAPTER:
        emit("HASHER_HOLD", reason="KEX_HASHER_ADAPTER_UNBOUND", job_id=job["job_id"])
        return None
    proc = subprocess.Popen(
        shlex.split(HASHER_ADAPTER),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    request = {"op": "HASH_JOB", "job": job}
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        err = proc.stderr.read(2048) if proc.stderr else ""
        raise RuntimeError("HASHER_NO_RECEIPT:" + err)
    result = json.loads(line)
    emit("HASHER_RECEIPT", job_id=job["job_id"], payload_root=canonical_root(result))
    return result


def validate_candidate(channel: StratumChannel, job: Dict[str, Any], c: Dict[str, Any]) -> None:
    if str(c.get("job_id")) != job["job_id"] or job["job_id"] != channel.current_job_id:
        raise ValueError("STALE_OR_JOB_MISMATCH")
    if str(c.get("route_id", job["route_id"])) != channel.route_id:
        raise ValueError("ORIGIN_ROUTE_MISMATCH")
    if str(c.get("worker", channel.worker)) != channel.worker:
        raise ValueError("WORKER_MISMATCH")
    en2 = str(c.get("extranonce2", ""))
    if len(en2) != 2 * channel.extranonce2_size:
        raise ValueError("EXTRANONCE2_WIDTH")
    nonce = str(c.get("nonce", ""))
    if len(nonce) != 8:
        raise ValueError("NONCE_WIDTH")
    if not c.get("hash_hex") or not c.get("header_hex"):
        raise ValueError("MISSING_CANDIDATE_PROOF")


def submit_candidate(channel: StratumChannel, job: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    validate_candidate(channel, job, candidate)
    params = [
        channel.worker,
        job["job_id"],
        candidate["extranonce2"],
        candidate.get("ntime", job["ntime"]),
        candidate["nonce"],
    ]
    if candidate.get("versionbits") is not None:
        params.append(candidate["versionbits"])
    rpc_id = channel.send("mining.submit", params)
    started = time.monotonic()
    response = channel.wait_response(rpc_id)
    state = "ACCEPTED" if response.get("result") is True and not response.get("error") else "REJECTED"
    receipt = {
        "state": state,
        "route_id": channel.route_id,
        "worker": channel.worker,
        "job_id": job["job_id"],
        "extranonce2": candidate["extranonce2"],
        "ntime": candidate.get("ntime", job["ntime"]),
        "nonce": candidate["nonce"],
        "rpc_id": rpc_id,
        "latency_ms": round((time.monotonic() - started) * 1000.0, 3),
        "response": response,
    }
    receipt["response_root"] = canonical_root(response)
    emit("SHARE_SUBMISSION", **receipt)
    return receipt


def main() -> int:
    channel: Optional[StratumChannel] = None
    try:
        channel = open_channel()
        emit("R12_CHANNEL_READY", route_id=channel.route_id, worker=channel.worker)
        while True:
            msg = channel.read_message()
            job = channel.handle_async(msg)
            if not job:
                continue
            result = dispatch_to_hasher(job)
            if not result:
                continue
            candidates = result.get("candidates") or ([] if not result.get("candidate") else [result["candidate"]])
            for candidate in candidates:
                submit_candidate(channel, job, candidate)
    except KeyboardInterrupt:
        emit("STOPPED", reason="SIGINT")
        return 130
    except Exception as exc:
        emit("R12_FAILURE", error=type(exc).__name__, detail=str(exc))
        return 1
    finally:
        if channel is not None:
            try:
                channel.stream.close()
            except Exception:
                pass
            try:
                channel.sock.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
