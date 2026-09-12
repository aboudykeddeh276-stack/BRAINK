from __future__ import annotations

import base64
import hashlib
import os
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .kex_stripe_client import KEXStripeClient, KEXStripeError

SYSTEM_ID = "app://casepath"
RUNTIME_URI = "KEX://RUNTIME/CASEPATH/CURRENT"
PAYMENT_AUTHORITY = "KEX://SECRETS/STRIPE/PAYMENT-RAIL"

PRODUCTS = {
    "MATTER_REVIEW": {
        "service_id": "KEX://CASEPATH/PRODUCT/MATTER_REVIEW",
        "plan": "default",
        "price_id": "price_1UEfvo0ZnkHf5Hg5607rPECW",
        "mode": "payment",
        "entitlement": "KEX://CASEPATH/ENTITLEMENT/MATTER_REVIEW",
    },
    "COMPLETE_PACK": {
        "service_id": "KEX://CASEPATH/PRODUCT/COMPLETE_PACK",
        "plan": "default",
        "price_id": "price_1UEfwH0ZnkHf5Hg5XlIZC5TV",
        "mode": "payment",
        "entitlement": "KEX://CASEPATH/ENTITLEMENT/COMPLETE_PACK",
    },
    "PRO_OFFICE_MONTHLY": {
        "service_id": "KEX://CASEPATH/PRODUCT/PRO_OFFICE_MONTHLY",
        "plan": "default",
        "price_id": "price_1UEfwk0ZnkHf5Hg5NskxrDxV",
        "mode": "subscription",
        "entitlement": "KEX://CASEPATH/ENTITLEMENT/PRO_OFFICE_MONTHLY",
    },
    "PRO_GROWTH_MONTHLY": {
        "service_id": "KEX://CASEPATH/PRODUCT/PRO_GROWTH_MONTHLY",
        "plan": "default",
        "price_id": "price_1UEfx60ZnkHf5Hg5WHtzbprO",
        "mode": "subscription",
        "entitlement": "KEX://CASEPATH/ENTITLEMENT/PRO_GROWTH_MONTHLY",
    },
}


class CheckoutRequest(BaseModel):
    browser_instance_id: str
    product: str
    success_url: str
    cancel_url: str


def build_router(*, saas, catalog, socket_path: str | None = None) -> APIRouter:
    router = APIRouter(prefix="/casepath", tags=["casepath-commerce"])
    kex = KEXStripeClient(socket_path or os.getenv("KEX_STRIPE_SOCKET", "/run/keddeh/kex-runner.sock"))

    def ensure_catalog() -> None:
        saas.register_system(
            SYSTEM_ID,
            "CasePath",
            PAYMENT_AUTHORITY,
            RUNTIME_URI,
            {"provider_role": "PROJECTION_ONLY"},
        )
        for key, spec in PRODUCTS.items():
            catalog.upsert_service(
                system_id=SYSTEM_ID,
                service_id=spec["service_id"],
                display_name=key,
                runtime_uri=RUNTIME_URI,
                plans={"default": {"stripe_price_id": spec["price_id"], "mode": spec["mode"]}},
                metadata={
                    "entitlement_uri": spec["entitlement"],
                    "provider_role": "PROJECTION_ONLY",
                },
            )

    @router.post("/checkout")
    def checkout(req: CheckoutRequest):
        spec = PRODUCTS.get(req.product)
        if not spec:
            raise HTTPException(404, "unknown CasePath product")
        if not req.success_url.startswith("https://") or not req.cancel_url.startswith("https://"):
            raise HTTPException(400, "https return URLs required")

        ensure_catalog()
        tenant_id = "casepath:" + hashlib.sha256(req.browser_instance_id.encode("utf-8")).hexdigest()[:32]
        saas.upsert_tenant(
            tenant_id,
            "CasePath browser session",
            {"identity_class": "OPAQUE_BROWSER_INSTANCE"},
        )
        admission = catalog.admit_checkout(
            tenant_id=tenant_id,
            system_id=SYSTEM_ID,
            service_id=spec["service_id"],
            plan="default",
        )
        try:
            provider = kex.call(
                "STRIPE_CREATE_CHECKOUT",
                {
                    "price_id": spec["price_id"],
                    "mode": spec["mode"],
                    "success_url": req.success_url,
                    "cancel_url": req.cancel_url,
                    "client_reference_id": tenant_id,
                    "metadata": {
                        "admission_id": admission["admission_id"],
                        "tenant_id": tenant_id,
                        "system_id": SYSTEM_ID,
                        "service_id": spec["service_id"],
                        "plan": "default",
                        "entitlement_uri": spec["entitlement"],
                    },
                },
            )
        except KEXStripeError as exc:
            raise HTTPException(503, f"KEX Stripe unavailable: {exc}") from exc

        catalog.bind_checkout(
            admission_id=admission["admission_id"],
            provider="stripe",
            provider_session_id=provider["session_id"],
            kex_receipt_id=provider.get("receipt_id"),
        )
        return {
            "status": "CHECKOUT_PENDING",
            "admission_id": admission["admission_id"],
            "session_id": provider["session_id"],
            "url": provider["url"],
        }

    @router.post("/stripe/webhook")
    async def webhook(
        request: Request,
        stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    ):
        if not stripe_signature:
            raise HTTPException(400, "missing Stripe-Signature")
        body = await request.body()
        try:
            verified = kex.call(
                "STRIPE_VERIFY_WEBHOOK",
                {
                    "body_b64": base64.b64encode(body).decode("ascii"),
                    "signature": stripe_signature,
                },
            )
        except KEXStripeError as exc:
            raise HTTPException(400, f"webhook verification failed: {exc}") from exc

        event = verified["event"]
        metadata = event.get("metadata") or {}
        if event["event_type"] != "checkout.session.completed":
            return {"status": "IGNORED", "event_id": event["event_id"]}

        required = ["admission_id", "tenant_id", "system_id", "service_id", "plan"]
        if any(not metadata.get(key) for key in required):
            raise HTTPException(409, "verified event missing KEX admission metadata")

        catalog.verify_provider_event(
            admission_id=metadata["admission_id"],
            provider="stripe",
            provider_session_id=event["object_id"],
            tenant_id=metadata["tenant_id"],
            system_id=metadata["system_id"],
            service_id=metadata["service_id"],
            plan=metadata["plan"],
        )
        payment_status = event.get("payment_status") or event.get("status") or "unknown"
        result = saas.process_verified_payment_event(
            provider="stripe",
            event_id=event["event_id"],
            event_type=event["event_type"],
            tenant_id=metadata["tenant_id"],
            system_id=metadata["system_id"],
            service_id=metadata["service_id"],
            plan=metadata["plan"],
            payment_status=payment_status,
            payload={
                "provider_session_id": event["object_id"],
                "kex_receipt_id": verified.get("receipt_id"),
            },
        )
        return {"status": "VERIFIED", "event_id": event["event_id"], "entitlement_result": result}

    return router
