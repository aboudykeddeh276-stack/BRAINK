from __future__ import annotations
from dataclasses import dataclass

SUCCESS={"CAPTURED","SETTLED","SUCCEEDED"}
FAIL={"DECLINED","FAILED","CANCELLED","REFUNDED","REVERSED"}

@dataclass
class Intent:
    intent_id: str
    account_ref: str
    sku: str
    amount_minor: int
    currency: str="AUD"
    state: str="CREATED"
    provider_reference: str|None=None
    entitled: bool=False

def apply_event(intent: Intent, event_id: str, event_type: str, provider_reference: str, seen: set[str]):
    if event_id in seen:
        return {"status":"IDEMPOTENT_REPLAY","entitled":intent.entitled}
    seen.add(event_id)
    kind=event_type.upper()
    intent.provider_reference=provider_reference
    if kind in SUCCESS:
        intent.state="PAID"
        intent.entitled=True
        return {"status":"ENTITLEMENT_ACTIVE","entitled":True}
    if kind in FAIL:
        intent.state=kind
        intent.entitled=False
        return {"status":"ENTITLEMENT_INACTIVE","entitled":False}
    intent.state="PENDING"
    return {"status":"PENDING","entitled":intent.entitled}

def provider_binding_state(env):
    return {
        "PAYPAL": bool(env.get("PAYPAL_CLIENT_ID") and env.get("PAYPAL_CLIENT_SECRET")),
        "AFTERPAY": bool(env.get("AFTERPAY_MERCHANT_ID") and env.get("AFTERPAY_SECRET_KEY")),
        "GOOGLE_PAY_GATEWAY": bool(env.get("GOOGLE_PAY_GATEWAY") and env.get("GOOGLE_PAY_MERCHANT_ID")),
    }
