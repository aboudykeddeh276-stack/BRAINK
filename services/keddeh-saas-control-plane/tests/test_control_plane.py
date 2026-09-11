import importlib, os, tempfile
from fastapi.testclient import TestClient

def client():
    td=tempfile.TemporaryDirectory(); os.environ["KEDDEH_SAAS_DB"]=td.name+"/test.sqlite3"; os.environ["KEDDEH_CONTROL_API_KEY"]="test-key"
    import keddeh_saas.app as mod; importlib.reload(mod)
    return td, TestClient(mod.app)

def test_health_and_quarantine():
    td,c=client();
    assert c.get("/health").json()["evidence_chain"] is True
    r=c.post("/v1/boundaries/probe",json={"source":"DNTG_RESEARCH","target":"SAAS_CONTROL","relation":"INVOKES"})
    assert r.status_code==200 and r.json()["allowed"] is False; td.cleanup()

def test_mutations_require_control_key():
    td,c=client();
    assert c.post("/v1/tenants",json={"product":"casepath","display_name":"X"}).status_code==401; td.cleanup()

def test_payment_idempotency_and_receipts():
    td,c=client(); h={"X-Keddeh-Control-Key":"test-key"}
    t=c.post("/v1/tenants",headers=h,json={"product":"casepath","display_name":"CasePath Test"}).json()["tenant"]
    p={"tenant_id":t["tenant_id"],"provider":"STRIPE","provider_reference":"pi_123","sku":"CP149","amount_minor":14900,"currency":"AUD","terminal_state":"SUCCEEDED"}
    a=c.post("/v1/billing/events",headers=h,json=p).json(); b=c.post("/v1/billing/events",headers=h,json=p).json()
    assert a["billing"]["capability_unlock"] is True
    assert b["receipt"]["event"]=="PAYMENT_EVENT_IDEMPOTENT_REPLAY"
    assert c.get("/v1/evidence").json()["chain_valid"] is True; td.cleanup()

def test_sqlite_persistence_across_reload():
    td,c=client(); h={"X-Keddeh-Control-Key":"test-key"}
    c.post("/v1/tenants",headers=h,json={"product":"claimpath","display_name":"ClaimPath"})
    before=c.get("/v1/evidence").json()["counts"]["tenants"]
    import keddeh_saas.app as mod; importlib.reload(mod); c2=TestClient(mod.app)
    assert before==1 and c2.get("/v1/evidence").json()["counts"]["tenants"]==1; td.cleanup()
