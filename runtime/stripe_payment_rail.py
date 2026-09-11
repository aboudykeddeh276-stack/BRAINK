#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import socket

SOCKET = os.environ.get("BRAINK_STRIPE_SOCKET", "/tmp/braink-stripe.sock")
KEX_RUNNER_SOCKET = os.environ.get("KEX_RUNNER_SOCKET", "/run/keddeh/kex-runner.sock")
KEX_PAYMENT_CAPABILITY = os.environ.get("KEX_PAYMENT_CAPABILITY", "kex://secrets/stripe/payment-rail")
KEX_CALLER_ID = os.environ.get("KEX_PAYMENT_CALLER_ID", "service://braink/stripe-payment-rail")


def reply(c: socket.socket, obj: dict) -> None:
    c.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())


def _recv_line(c: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(65536)
        if not chunk:
            break
        data += chunk
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("KEX_RESPONSE_TOO_LARGE")
    return data


def kex_execute(operation: str, payload: dict) -> dict:
    request = {
        "op": "EXECUTE_CAPABILITY",
        "caller": KEX_CALLER_ID,
        "capability": KEX_PAYMENT_CAPABILITY,
        "operation": operation,
        "payload": payload,
        "result_policy": "SANITIZED_NO_SECRET_MATERIAL",
    }
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(25)
        s.connect(KEX_RUNNER_SOCKET)
        s.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
        raw = _recv_line(s)
    if not raw:
        raise RuntimeError("KEX_RUNNER_EMPTY_RESPONSE")
    result = json.loads(raw.decode())
    if result.get("status") != "PASS":
        raise PermissionError(result.get("error", "KEX_EXECUTION_REJECTED"))
    return result


def create_checkout(req: dict) -> dict:
    domain = req.get("domain", "braink.com.au")
    product = req.get("product", "BRAINK")
    result = kex_execute(
        "STRIPE_CREATE_CHECKOUT",
        {
            "domain": domain,
            "product": product,
            "tenant_id": req.get("tenant_id"),
            "service_id": req.get("service_id"),
            "plan": req.get("plan"),
        },
    )
    out = result.get("result") or {}
    if not out.get("checkout_url") or not out.get("session_id"):
        raise RuntimeError("KEX_STRIPE_CHECKOUT_RESULT_INCOMPLETE")
    return {
        "checkout_url": out["checkout_url"],
        "session_id": out["session_id"],
        "kex_receipt_id": result.get("receipt_id"),
    }


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    result = kex_execute(
        "STRIPE_VERIFY_WEBHOOK",
        {
            "payload_b64": base64.b64encode(payload).decode(),
            "stripe_signature": sig_header,
        },
    )
    event = (result.get("result") or {}).get("event")
    if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
        raise RuntimeError("KEX_STRIPE_WEBHOOK_RESULT_INCOMPLETE")
    return event


def handle(c: socket.socket) -> None:
    line = _recv_line(c)
    if not line:
        return reply(c, {"status": "REJECTED", "error": "EMPTY_REQUEST"})
    req = json.loads(line.decode())
    op = req.get("op")
    if op == "CREATE_CHECKOUT":
        return reply(c, {"status": "PASS", **create_checkout(req.get("request") or {})})
    if op == "WEBHOOK":
        payload = base64.b64decode(req.get("payload_b64", ""), validate=True)
        event = verify_webhook(payload, req.get("stripe_signature", ""))
        return reply(c, {"status": "PASS", "event": event})
    return reply(c, {"status": "REJECTED", "error": "UNKNOWN_OPERATION"})


def main() -> None:
    try:
        os.unlink(SOCKET)
    except FileNotFoundError:
        pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(SOCKET)
    os.chmod(SOCKET, 0o660)
    s.listen(32)
    while True:
        c, _ = s.accept()
        try:
            handle(c)
        except Exception as e:
            reply(c, {"status": "REJECTED", "error": type(e).__name__ + ":" + str(e)})
        finally:
            c.close()


if __name__ == "__main__":
    main()
