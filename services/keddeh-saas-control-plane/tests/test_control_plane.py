import importlib
import os
import tempfile

from fastapi.testclient import TestClient


def client():
    td = tempfile.TemporaryDirectory()
    os.environ["KEDDEH_SAAS_DB"] = td.name + "/test.sqlite3"
    os.environ["BRAINK_SAAS_STATE_DIR"] = td.name + "/braink"
    os.environ["KEDDEH_CONTROL_API_KEY"] = "test-key"
    import keddeh_saas.app as mod
    importlib.reload(mod)
    return td, mod, TestClient(mod.app)


def test_health_quarantine_and_catalog_do_not_overclaim():
    td, mod, c = client()
    health = c.get("/health").json()
    assert health["local_evidence_chain"] is True

    r = c.post(
        "/v1/boundaries/probe",
        json={
            "source": "DNTG_RESEARCH",
            "target": "SAAS_CONTROL",
            "relation": "INVOKES",
        },
    )
    assert r.status_code == 200 and r.json()["allowed"] is False

    catalog = c.get("/v1/catalog").json()
    assert "braink-illlm-evidence-bridge" in catalog["implemented"]
    assert "public-production-deployment" in catalog["declared_unbound"]
    assert "casepath-saas-adapter-description" in catalog["descriptor_only"]

    casepath = c.get("/v1/adapters/casepath").json()
    claimpath = c.get("/v1/adapters/claimpath").json()
    assert casepath["implementation_state"] == "DESCRIPTOR_ONLY"
    assert claimpath["implementation_state"] == "DESCRIPTOR_ONLY"
    td.cleanup()


def test_mutations_require_control_key():
    td, mod, c = client()
    assert c.post(
        "/v1/tenants",
        json={"product": "casepath", "display_name": "X"},
    ).status_code == 401
    td.cleanup()


def test_payment_idempotency_receipts_and_braink_evidence():
    td, mod, c = client()
    h = {"X-Keddeh-Control-Key": "test-key"}
    tenant_response = c.post(
        "/v1/tenants",
        headers=h,
        json={"product": "casepath", "display_name": "CasePath Test"},
    ).json()
    assert tenant_response["braink_evidence"]["status"] == "SYNCED"
    t = tenant_response["tenant"]

    p = {
        "tenant_id": t["tenant_id"],
        "provider": "STRIPE",
        "provider_reference": "pi_123",
        "sku": "CP149",
        "amount_minor": 14900,
        "currency": "AUD",
        "terminal_state": "SUCCEEDED",
    }
    a = c.post("/v1/billing/events", headers=h, json=p).json()
    b = c.post("/v1/billing/events", headers=h, json=p).json()
    assert a["billing"]["capability_unlock"] is True
    assert a["braink_evidence"]["status"] == "SYNCED"
    assert b["receipt"]["event"] == "PAYMENT_EVENT_IDEMPOTENT_REPLAY"
    assert b["braink_evidence"]["status"] == "SYNCED"

    evidence = c.get("/v1/evidence").json()
    assert evidence["local"]["chain_valid"] is True
    assert evidence["local"]["braink_evidence_pending"] == []
    assert evidence["braink"]["status"] == "PASS"
    td.cleanup()


def test_sqlite_and_braink_state_persist_across_reload():
    td, mod, c = client()
    h = {"X-Keddeh-Control-Key": "test-key"}
    c.post(
        "/v1/tenants",
        headers=h,
        json={"product": "claimpath", "display_name": "ClaimPath"},
    )
    before = c.get("/v1/evidence").json()
    importlib.reload(mod)
    c2 = TestClient(mod.app)
    after = c2.get("/v1/evidence").json()
    assert before["local"]["counts"]["tenants"] == 1
    assert after["local"]["counts"]["tenants"] == 1
    assert before["braink"]["illlm_ledger"]["events"] == after["braink"]["illlm_ledger"]["events"]
    td.cleanup()


def test_runtime_admission_preserves_existing_definition():
    td, mod, c = client()
    h = {"X-Keddeh-Control-Key": "test-key"}
    rid = "runtime://braink/saas-control-plane"
    mod.braink.registry.upsert(
        {
            "runtime_id": rid,
            "runtime_class": "EXISTING_WORKING_RUNTIME",
            "command_route": "existing-working-command",
            "argv": ["--preserve-me"],
            "desired_state": "RUNNING",
            "observed_state": "RUNNING",
            "generation": 9,
            "restart_count": 0,
        }
    )
    before = mod.braink.registry.inflate(mod.braink.registry.get(rid))
    result = c.post("/v1/braink/runtime/admit", headers=h).json()
    after = mod.braink.registry.inflate(mod.braink.registry.get(rid))

    assert result["status"] == "PRESERVED_EXISTING"
    assert result["mutated"] is False
    assert result["compatible_with_candidate"] is False
    assert before == after
    assert after["command_route"] == "existing-working-command"
    assert after["observed_state"] == "RUNNING"
    td.cleanup()
