#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

DEFAULT_SOCKET = "/run/keddeh/kex-runner.sock"
PAYMENT_CAPABILITY = "kex://secrets/stripe/payment-rail"
ALLOWED_OPERATIONS = {"STRIPE_CREATE_CHECKOUT", "STRIPE_VERIFY_WEBHOOK"}
RESULT_POLICY = "SANITIZED_NO_SECRET_MATERIAL"
MAX_MESSAGE = 4 * 1024 * 1024


class CapabilityError(RuntimeError):
    pass


class SecretResolver:
    """KEX-owned secret resolver boundary."""

    def __init__(self, command: str | None = None):
        self.command = command or os.environ.get("KEX_SECRET_RESOLVER", "")

    def resolve(self, capability: str) -> dict[str, str]:
        if not self.command:
            raise CapabilityError("KEX_SECRET_RESOLVER_UNBOUND")
        proc = subprocess.run(
            [self.command, "resolve", capability],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        if proc.returncode != 0:
            raise CapabilityError("KEX_SECRET_RESOLUTION_DENIED")
        try:
            data = json.loads(proc.stdout)
        except Exception as exc:
            raise CapabilityError("KEX_SECRET_RESOLUTION_INVALID") from exc
        if not isinstance(data, dict):
            raise CapabilityError("KEX_SECRET_RESOLUTION_INVALID")
        return {str(k): str(v) for k, v in data.items() if v is not None}


def _stripe_request(secret_key: str, path: str, form: dict[str, Any]) -> dict[str, Any]:
    encoded = urllib.parse.urlencode(form, doseq=True).encode()
    req = urllib.request.Request(
        "https://api.stripe.com" + path,
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "KEX-Capability-Runner/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
    except Exception as exc:
        raise CapabilityError("STRIPE_PROVIDER_REQUEST_FAILED") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CapabilityError("STRIPE_PROVIDER_RESPONSE_INVALID") from exc
    if not isinstance(payload, dict):
        raise CapabilityError("STRIPE_PROVIDER_RESPONSE_INVALID")
    return payload


def _checkout_form(payload: dict[str, Any]) -> dict[str, Any]:
    domain = str(payload.get("domain") or "braink.com.au").strip()
    product = str(payload.get("product") or "BRAINK").strip()
    plan = payload.get("plan") or {}
    if isinstance(plan, str):
        plan = {"stripe_price_id": plan}
    if not isinstance(plan, dict):
        raise CapabilityError("STRIPE_PLAN_INVALID")
    form: dict[str, Any] = {
        "mode": str(plan.get("mode") or "subscription"),
        "success_url": str(plan.get("success_url") or f"https://{domain}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"),
        "cancel_url": str(plan.get("cancel_url") or f"https://{domain}/billing/cancel"),
        "client_reference_id": str(payload.get("tenant_id") or "")[:200],
        "metadata[tenant_id]": str(payload.get("tenant_id") or "")[:500],
        "metadata[service_id]": str(payload.get("service_id") or "")[:500],
        "metadata[product]": product[:500],
    }
    price_id = str(plan.get("stripe_price_id") or plan.get("price_id") or "").strip()
    if price_id:
        form["line_items[0][price]"] = price_id
        form["line_items[0][quantity]"] = int(plan.get("quantity") or 1)
        return form
    amount = plan.get("unit_amount")
    if amount is None:
        raise CapabilityError("STRIPE_PRICE_BINDING_REQUIRED")
    form.update({
        "line_items[0][price_data][currency]": str(plan.get("currency") or "aud").lower(),
        "line_items[0][price_data][unit_amount]": int(amount),
        "line_items[0][price_data][product_data][name]": str(plan.get("name") or product)[:200],
        "line_items[0][quantity]": int(plan.get("quantity") or 1),
    })
    if form["mode"] == "subscription":
        form["line_items[0][price_data][recurring][interval]"] = str(plan.get("interval") or "month")
    return form


def _verify_stripe_signature(payload: bytes, header: str, secret: str, tolerance: int = 300) -> None:
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        parts.setdefault(k.strip(), []).append(v.strip())
    try:
        ts = int(parts["t"][0])
    except Exception as exc:
        raise CapabilityError("STRIPE_SIGNATURE_HEADER_INVALID") from exc
    if abs(int(time.time()) - ts) > tolerance:
        raise CapabilityError("STRIPE_SIGNATURE_TIMESTAMP_OUTSIDE_TOLERANCE")
    signed = str(ts).encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
        raise CapabilityError("STRIPE_SIGNATURE_INVALID")


def _sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    obj = ((event.get("data") or {}).get("object") or {}) if isinstance(event.get("data"), dict) else {}
    safe_obj = {
        k: obj.get(k)
        for k in ("id", "object", "customer", "subscription", "payment_status", "status", "mode", "client_reference_id", "metadata")
        if k in obj
    }
    return {
        "id": event.get("id"),
        "type": event.get("type"),
        "created": event.get("created"),
        "livemode": event.get("livemode"),
        "data": {"object": safe_obj},
    }


class KEXCapabilityRunner:
    def __init__(self, *, resolver: SecretResolver | Any | None = None, stripe_transport: Callable[[str, str, dict[str, Any]], dict[str, Any]] = _stripe_request, authority_check: Callable[[dict[str, Any]], bool] | None = None, ledger_path: str | Path | None = None):
        self.resolver = resolver or SecretResolver()
        self.stripe_transport = stripe_transport
        self.authority_check = authority_check or self._default_authority_check
        self.ledger_path = Path(ledger_path or os.environ.get("KEX_CAPABILITY_LEDGER", "/var/lib/braink/kex/capability-ledger.jsonl"))

    @staticmethod
    def _default_authority_check(request: dict[str, Any]) -> bool:
        caller = str(request.get("caller") or "")
        allowed = {x.strip() for x in os.environ.get("KEX_CAPABILITY_CALLERS", "service://braink/stripe-payment-rail").split(",") if x.strip()}
        return caller in allowed

    def _receipt(self, request: dict[str, Any], status: str, error: str | None = None) -> str:
        receipt = {
            "schema": "kex.capability-execution.receipt.v1",
            "receipt_id": f"KEXCAP-{uuid.uuid4().hex[:16]}",
            "timestamp": time.time(),
            "status": status,
            "capability": request.get("capability"),
            "operation": request.get("operation"),
            "caller": request.get("caller"),
            "result_policy": request.get("result_policy"),
            "error": error,
            "secret_material_returned": False,
        }
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt, sort_keys=True) + "\n")
        except OSError:
            pass
        return receipt["receipt_id"]

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("op") != "EXECUTE_CAPABILITY":
            return {"status": "REJECTED", "error": "UNKNOWN_OPERATION"}
        if request.get("capability") != PAYMENT_CAPABILITY:
            return {"status": "REJECTED", "error": "CAPABILITY_NOT_REGISTERED"}
        operation = str(request.get("operation") or "")
        if operation not in ALLOWED_OPERATIONS:
            return {"status": "REJECTED", "error": "OPERATION_NOT_AUTHORIZED"}
        if request.get("result_policy") != RESULT_POLICY:
            return {"status": "REJECTED", "error": "RESULT_POLICY_REQUIRED"}
        if not self.authority_check(request):
            return {"status": "REJECTED", "error": "CALLER_NOT_AUTHORIZED"}
        try:
            secrets = self.resolver.resolve(PAYMENT_CAPABILITY)
            payload = request.get("payload") or {}
            if operation == "STRIPE_CREATE_CHECKOUT":
                key = secrets.get("secret_key") or secrets.get("stripe_secret_key")
                if not key:
                    raise CapabilityError("STRIPE_SECRET_KEY_UNAVAILABLE")
                provider = self.stripe_transport(key, "/v1/checkout/sessions", _checkout_form(payload))
                session_id = provider.get("id")
                checkout_url = provider.get("url")
                if not session_id or not checkout_url:
                    raise CapabilityError("STRIPE_CHECKOUT_RESPONSE_INCOMPLETE")
                result = {"session_id": session_id, "checkout_url": checkout_url}
            else:
                whsec = secrets.get("webhook_secret") or secrets.get("stripe_webhook_secret")
                if not whsec:
                    raise CapabilityError("STRIPE_WEBHOOK_SECRET_UNAVAILABLE")
                try:
                    raw = base64.b64decode(str(payload.get("payload_b64") or ""), validate=True)
                except Exception as exc:
                    raise CapabilityError("STRIPE_WEBHOOK_PAYLOAD_INVALID") from exc
                _verify_stripe_signature(raw, str(payload.get("stripe_signature") or ""), whsec)
                try:
                    event = json.loads(raw.decode("utf-8"))
                except Exception as exc:
                    raise CapabilityError("STRIPE_WEBHOOK_JSON_INVALID") from exc
                if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
                    raise CapabilityError("STRIPE_WEBHOOK_EVENT_INVALID")
                result = {"event": _sanitize_event(event)}
            receipt_id = self._receipt(request, "PASS")
            return {"status": "PASS", "receipt_id": receipt_id, "result": result}
        except CapabilityError as exc:
            receipt_id = self._receipt(request, "REJECTED", str(exc))
            return {"status": "REJECTED", "receipt_id": receipt_id, "error": str(exc)}
        except Exception:
            receipt_id = self._receipt(request, "REJECTED", "CAPABILITY_EXECUTION_FAILED")
            return {"status": "REJECTED", "receipt_id": receipt_id, "error": "CAPABILITY_EXECUTION_FAILED"}


def _recv_line(conn: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
        if len(data) > MAX_MESSAGE:
            raise CapabilityError("REQUEST_TOO_LARGE")
    return data


def serve(socket_path: str | None = None) -> None:
    path = Path(socket_path or os.environ.get("KEX_RUNNER_SOCKET", DEFAULT_SOCKET))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    os.chmod(path, int(os.environ.get("KEX_RUNNER_SOCKET_MODE", "660"), 8))
    server.listen(32)
    runner = KEXCapabilityRunner()
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    raw = _recv_line(conn)
                    request = json.loads(raw.decode("utf-8")) if raw else {}
                    response = runner.execute(request if isinstance(request, dict) else {})
                except Exception:
                    response = {"status": "REJECTED", "error": "INVALID_REQUEST"}
                conn.sendall((json.dumps(response, separators=(",", ":")) + "\n").encode())
    finally:
        server.close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    serve()
