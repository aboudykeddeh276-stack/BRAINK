#!/usr/bin/env python3
import base64
import hashlib
import hmac
import importlib.util
import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / "modules" / "kex_wbos" / "capability_runner.py"
spec = importlib.util.spec_from_file_location("capability_runner", MOD)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Resolver:
    def resolve(self, capability):
        assert capability == m.PAYMENT_CAPABILITY
        return {"secret_key": "sk_test_INTERNAL_ONLY", "webhook_secret": "whsec_INTERNAL_ONLY"}


def transport(secret, path, form):
    assert secret == "sk_test_INTERNAL_ONLY"
    assert path == "/v1/checkout/sessions"
    assert form["metadata[tenant_id]"] == "TENANT-1"
    return {"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"}


with tempfile.TemporaryDirectory() as td:
    runner = m.KEXCapabilityRunner(
        resolver=Resolver(),
        stripe_transport=transport,
        authority_check=lambda r: r.get("caller") == "service://braink/stripe-payment-rail",
        ledger_path=Path(td) / "ledger.jsonl",
    )
    base = {
        "op": "EXECUTE_CAPABILITY",
        "capability": m.PAYMENT_CAPABILITY,
        "result_policy": m.RESULT_POLICY,
        "caller": "service://braink/stripe-payment-rail",
    }
    denied = runner.execute({**base, "caller": "service://evil", "operation": "STRIPE_CREATE_CHECKOUT", "payload": {}})
    assert denied["status"] == "REJECTED"

    checkout = runner.execute({
        **base,
        "operation": "STRIPE_CREATE_CHECKOUT",
        "payload": {
            "domain": "braink.com.au",
            "tenant_id": "TENANT-1",
            "service_id": "svc",
            "plan": {"unit_amount": 1000, "currency": "aud", "mode": "payment"},
        },
    })
    assert checkout["status"] == "PASS"
    assert checkout["result"]["session_id"] == "cs_test_123"

    raw = json.dumps({
        "id": "evt_1",
        "type": "checkout.session.completed",
        "created": 1,
        "livemode": False,
        "data": {"object": {
            "id": "cs_test_123",
            "customer": "cus_1",
            "payment_status": "paid",
            "metadata": {"tenant_id": "TENANT-1"},
            "secret": "MUST_NOT_ESCAPE",
        }},
    }, separators=(",", ":")).encode()
    ts = int(time.time())
    sig = hmac.new(b"whsec_INTERNAL_ONLY", str(ts).encode() + b"." + raw, hashlib.sha256).hexdigest()
    webhook = runner.execute({
        **base,
        "operation": "STRIPE_VERIFY_WEBHOOK",
        "payload": {
            "payload_b64": base64.b64encode(raw).decode(),
            "stripe_signature": f"t={ts},v1={sig}",
        },
    })
    assert webhook["status"] == "PASS"
    rendered = json.dumps(webhook)
    assert "INTERNAL_ONLY" not in rendered
    assert "MUST_NOT_ESCAPE" not in rendered
    assert webhook["result"]["event"]["data"]["object"]["payment_status"] == "paid"
    ledger = (Path(td) / "ledger.jsonl").read_text()
    assert "INTERNAL_ONLY" not in ledger

print("KEX_CAPABILITY_RUNNER_PASS")
