from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import braink_runtime.casepath_stripe as cp


class FakeSaaS:
    def __init__(self):
        self.events=[]
    def register_system(self,*args,**kwargs): return {"ok":True}
    def upsert_tenant(self,*args,**kwargs): return {"ok":True}
    def process_verified_payment_event(self,**kwargs):
        self.events.append(kwargs)
        return {"status":"ENTITLEMENT_ACTIVE"}


class FakeCatalog:
    def __init__(self):
        self.bound=None; self.verified=None; self.services=[]
    def upsert_service(self,**kwargs): self.services.append(kwargs); return kwargs
    def admit_checkout(self,**kwargs): return {"admission_id":"adm_test","status":"ADMITTED",**kwargs}
    def bind_checkout(self,**kwargs): self.bound=kwargs; return {"status":"BOUND",**kwargs}
    def verify_provider_event(self,**kwargs): self.verified=kwargs; return {"status":"VERIFIED",**kwargs}


class FakeKEX:
    last_payload=None
    def __init__(self,*args,**kwargs): pass
    def call(self,op,payload):
        FakeKEX.last_payload=(op,payload)
        if op=="STRIPE_CREATE_CHECKOUT":
            return {"status":"PASS","receipt_id":"r1","session_id":"cs_test_1","url":"https://checkout.stripe.com/c/pay/test"}
        return {"status":"PASS","receipt_id":"r2","event":{
            "event_id":"evt_test_1","event_type":"checkout.session.completed","object_id":"cs_test_1",
            "payment_status":"paid","status":"complete","metadata":{
                "admission_id":"adm_test","tenant_id":"casepath:opaque","system_id":cp.SYSTEM_ID,
                "service_id":cp.PRODUCTS["MATTER_REVIEW"]["service_id"],"plan":"default"
            }
        }}


def make_client(monkeypatch):
    monkeypatch.setattr(cp,"KEXStripeClient",FakeKEX)
    saas=FakeSaaS(); catalog=FakeCatalog(); app=FastAPI()
    app.include_router(cp.build_router(saas=saas,catalog=catalog,socket_path="/tmp/fake.sock"))
    return TestClient(app),saas,catalog


def test_checkout_is_whitelisted_and_contains_no_matter_body(monkeypatch):
    client,_,catalog=make_client(monkeypatch)
    response=client.post("/casepath/checkout",json={
        "browser_instance_id":"opaque-browser-id",
        "product":"MATTER_REVIEW",
        "success_url":"https://casepath.com.au/?checkout=success",
        "cancel_url":"https://casepath.com.au/?checkout=cancelled"
    })
    assert response.status_code==200
    assert response.json()["status"]=="CHECKOUT_PENDING"
    op,payload=FakeKEX.last_payload
    assert op=="STRIPE_CREATE_CHECKOUT"
    assert payload["price_id"]==cp.PRODUCTS["MATTER_REVIEW"]["price_id"]
    assert "matter" not in " ".join(payload["metadata"].keys()).lower()
    assert catalog.bound["provider_session_id"]=="cs_test_1"


def test_unknown_product_cannot_select_arbitrary_price(monkeypatch):
    client,_,_=make_client(monkeypatch)
    response=client.post("/casepath/checkout",json={
        "browser_instance_id":"opaque-browser-id","product":"FAKE_PRICE",
        "success_url":"https://casepath.com.au/","cancel_url":"https://casepath.com.au/"
    })
    assert response.status_code==404


def test_entitlement_only_after_verified_webhook(monkeypatch):
    client,saas,catalog=make_client(monkeypatch)
    assert saas.events==[]
    response=client.post("/casepath/stripe/webhook",content=b"{}",headers={"stripe-signature":"t=1,v1=test"})
    assert response.status_code==200
    assert response.json()["status"]=="VERIFIED"
    assert catalog.verified["provider_session_id"]=="cs_test_1"
    assert len(saas.events)==1
    assert saas.events[0]["payment_status"]=="paid"
