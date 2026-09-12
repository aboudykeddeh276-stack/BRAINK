from __future__ import annotations

import base64
import json
import os
import shlex
import socket
import subprocess
import time
from pathlib import Path

import stripe

SOCKET_PATH = os.getenv("KEX_STRIPE_SOCKET", "/run/keddeh/kex-runner.sock")
SECRET_RESOLVER = os.getenv("KEX_STRIPE_SECRET_RESOLVER", "")
WEBHOOK_RESOLVER = os.getenv("KEX_STRIPE_WEBHOOK_SECRET_RESOLVER", "")
LEDGER = Path(os.getenv("KEX_STRIPE_LEDGER", "/var/lib/braink/kex/stripe-capability-ledger.jsonl"))
ALLOWED_OPS = {"STRIPE_CREATE_CHECKOUT", "STRIPE_VERIFY_WEBHOOK"}


def resolve_secret(command: str) -> str:
    if not command:
        raise RuntimeError("secret resolver is not configured")
    proc = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=5, check=True)
    secret = proc.stdout.strip()
    if not secret:
        raise RuntimeError("secret resolver returned empty secret")
    return secret


def append_receipt(op: str, status: str, provider_id: str | None = None) -> str:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts_ns": time.time_ns(),
        "capability": "KEX://SECRETS/STRIPE/PAYMENT-RAIL",
        "op": op,
        "status": status,
        "provider_id": provider_id,
    }
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return f"kex-stripe-{row['ts_ns']}"


def create_checkout(payload: dict) -> dict:
    stripe.api_key = resolve_secret(SECRET_RESOLVER)
    mode = payload["mode"]
    if mode not in {"payment", "subscription"}:
        raise ValueError("unsupported checkout mode")
    metadata = {str(k): str(v) for k, v in payload.get("metadata", {}).items()}
    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price": payload["price_id"], "quantity": 1}],
        success_url=payload["success_url"],
        cancel_url=payload["cancel_url"],
        client_reference_id=payload.get("client_reference_id"),
        metadata=metadata,
    )
    receipt_id = append_receipt("STRIPE_CREATE_CHECKOUT", "PASS", session.id)
    return {"status": "PASS", "receipt_id": receipt_id, "session_id": session.id, "url": session.url}


def verify_webhook(payload: dict) -> dict:
    endpoint_secret = resolve_secret(WEBHOOK_RESOLVER)
    body = base64.b64decode(payload["body_b64"])
    event = stripe.Webhook.construct_event(body, payload["signature"], endpoint_secret)
    obj = event["data"]["object"]
    clean = {
        "event_id": event["id"],
        "event_type": event["type"],
        "object_id": obj.get("id"),
        "payment_status": obj.get("payment_status"),
        "status": obj.get("status"),
        "metadata": dict(obj.get("metadata") or {}),
        "client_reference_id": obj.get("client_reference_id"),
    }
    receipt_id = append_receipt("STRIPE_VERIFY_WEBHOOK", "PASS", event["id"])
    return {"status": "PASS", "receipt_id": receipt_id, "event": clean}


def dispatch(request: dict) -> dict:
    op = request.get("op")
    payload = request.get("payload") or {}
    if op not in ALLOWED_OPS:
        return {"status": "DENIED", "error": "operation not allowed"}
    try:
        return create_checkout(payload) if op == "STRIPE_CREATE_CHECKOUT" else verify_webhook(payload)
    except Exception as exc:
        append_receipt(op or "UNKNOWN", "FAIL", None)
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}


def serve() -> None:
    path = Path(SOCKET_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        server.listen(64)
        while True:
            conn, _ = server.accept()
            with conn:
                raw = b""
                while b"\n" not in raw:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    raw += chunk
                if not raw:
                    continue
                try:
                    response = dispatch(json.loads(raw.split(b"\n", 1)[0]))
                except Exception as exc:
                    response = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
                conn.sendall((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))


if __name__ == "__main__":
    serve()
