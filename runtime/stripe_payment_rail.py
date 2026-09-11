#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import socket
import urllib.error
import urllib.request

SOCKET = os.environ.get("BRAINK_STRIPE_SOCKET", "/tmp/braink-stripe.sock")
KEX_RUNNER_SOCKET = os.environ.get("KEX_RUNNER_SOCKET", "/run/keddeh/kex-runner.sock")
KEX_PAYMENT_CAPABILITY = os.environ.get("KEX_PAYMENT_CAPABILITY", "kex://secrets/stripe/payment-rail")
KEX_CALLER_ID = os.environ.get("KEX_PAYMENT_CALLER_ID", "service://braink/stripe-payment-rail")
BRAINK_SAAS_ENDPOINT = os.environ.get("BRAINK_SAAS_ENDPOINT", "http://127.0.0.1:8000").rstrip("/")
BRAINK_SAAS_AUTH_TOKEN = os.environ.get("BRAINK_SAAS_AUTH_TOKEN") or os.environ.get("BRAINK_AUTH_TOKEN", "")
SUPPORTED_SAAS_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
}


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


def _saas_post(path: str, payload: dict) -> dict:
    if not BRAINK_SAAS_AUTH_TOKEN:
        raise RuntimeError("BRAINK_SAAS_AUTH_TOKEN_NOT_CONFIGURED")
    body = json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        BRAINK_SAAS_ENDPOINT + path,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "x-braink-token": BRAINK_SAAS_AUTH_TOKEN},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:4096]
        raise RuntimeError(f"SAAS_HTTP_{exc.code}:{detail}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("SAAS_RESPONSE_INVALID")
    return result


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
    tenant_id = str(req.get("tenant_id") or "").strip()
    system_id = str(req.get("system_id") or "").strip()
    service_id = str(req.get("service_id") or "").strip()
    plan_id = str(req.get("plan") or "").strip()
    if not tenant_id or not system_id or not service_id or not plan_id:
        raise ValueError("SAAS_CHECKOUT_ROUTE_REQUIRED")
    admission = _saas_post(
        "/saas/checkout-admission",
        {"tenant_id": tenant_id, "system_id": system_id, "service_id": service_id, "plan": plan_id},
    )
    if admission.get("status") != "ADMITTED":
        raise PermissionError("SAAS_CHECKOUT_NOT_ADMITTED")
    provider_plan = admission.get("provider_plan")
    if not isinstance(provider_plan, dict) or provider_plan.get("plan_id") != plan_id:
        raise RuntimeError("SAAS_PROVIDER_PLAN_INVALID")
    domain = req.get("domain", "braink.com.au")
    product = req.get("product", admission.get("service_id") or "BRAINK")
    result = kex_execute(
        "STRIPE_CREATE_CHECKOUT",
        {
            "domain": domain,
            "product": product,
            "tenant_id": tenant_id,
            "system_id": system_id,
            "service_id": service_id,
            "plan": provider_plan,
        },
    )
    out = result.get("result") or {}
    if not out.get("checkout_url") or not out.get("session_id"):
        raise RuntimeError("KEX_STRIPE_CHECKOUT_RESULT_INCOMPLETE")
    return {
        "checkout_url": out["checkout_url"],
        "session_id": out["session_id"],
        "kex_receipt_id": result.get("receipt_id"),
        "admitted": {"tenant_id": tenant_id, "system_id": system_id, "service_id": service_id, "plan": plan_id},
    }


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    result = kex_execute(
        "STRIPE_VERIFY_WEBHOOK",
        {"payload_b64": base64.b64encode(payload).decode(), "stripe_signature": sig_header},
    )
    event = (result.get("result") or {}).get("event")
    if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
        raise RuntimeError("KEX_STRIPE_WEBHOOK_RESULT_INCOMPLETE")
    return event


def _saas_payload_from_event(event: dict) -> dict | None:
    event_type = str(event.get("type", ""))
    if event_type not in SUPPORTED_SAAS_EVENTS:
        return None
    obj = ((event.get("data") or {}).get("object") or {})
    metadata = obj.get("metadata") or {}
    required = ("tenant_id", "system_id", "service_id", "plan")
    missing = [key for key in required if not str(metadata.get(key, "")).strip()]
    if missing:
        raise ValueError("SAAS_PAYMENT_METADATA_MISSING:" + ",".join(missing))
    payment_status = str(obj.get("payment_status") or obj.get("status") or "").lower()
    if not payment_status:
        if event_type == "checkout.session.async_payment_succeeded":
            payment_status = "succeeded"
        elif event_type == "checkout.session.async_payment_failed":
            payment_status = "failed"
        else:
            raise ValueError("SAAS_PAYMENT_STATUS_MISSING")
    return {
        "provider": "stripe",
        "event_id": str(event["id"]),
        "event_type": event_type,
        "tenant_id": str(metadata["tenant_id"]),
        "system_id": str(metadata["system_id"]),
        "service_id": str(metadata["service_id"]),
        "plan": str(metadata["plan"]),
        "payment_status": payment_status,
        "payload": {"checkout_session_id": obj.get("id"), "customer": obj.get("customer"), "subscription": obj.get("subscription")},
    }


def activate_saas(event: dict) -> dict:
    payload = _saas_payload_from_event(event)
    if payload is None:
        return {"processing_status": "IGNORED_EVENT_TYPE", "event_type": event.get("type")}
    result = _saas_post("/saas/payments/verified-event", payload)
    if result.get("processing_status") not in {"ENTITLED_PENDING_ACTUATION", "IGNORED_NOT_PAID"}:
        raise RuntimeError("SAAS_ACTIVATION_RESULT_INVALID")
    return result


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
        activation = activate_saas(event)
        return reply(c, {"status": "PASS", "event": event, "saas_activation": activation})
    return reply(c, {"status": "REJECTED", "error": "UNKNOWN_OPERATION"})


def main() -> None:
    try:
        os.unlink(SOCKET)
    except FileNotFoundError:
        pass
    Path = __import__('pathlib').Path
    Path(SOCKET).parent.mkdir(parents=True, exist_ok=True)
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
