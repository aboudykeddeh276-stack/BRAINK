import importlib
import os
import tempfile

from fastapi.testclient import TestClient


def client(tmp):
    os.environ['BRAINK_DATA_DIR'] = tmp
    os.environ['BRAINK_AUTH_TOKEN'] = 'test-token'
    import braink_runtime.app as m
    importlib.reload(m)
    return TestClient(m.app)


def test_checkout_requires_registered_tenant_service_and_plan():
    with tempfile.TemporaryDirectory() as d:
        c = client(d)
        h = {'x-braink-token': 'test-token'}
        assert c.put('/saas/systems/braink', json={
            'system_id': 'braink',
            'name': 'BRAINK',
            'adapter_uri': 'adapter://braink',
            'runtime_uri': 'runtime://braink/core',
        }, headers=h).status_code == 200
        assert c.put('/saas/tenants/acme', json={
            'tenant_id': 'acme', 'display_name': 'ACME'
        }, headers=h).status_code == 200
        service = {
            'system_id': 'braink',
            'service_id': 'agent',
            'display_name': 'BRAINK Agent',
            'runtime_uri': 'runtime://braink/tenant-agent',
            'plans': {
                'pro': {
                    'stripe_price_id': 'price_test_pro',
                    'mode': 'subscription',
                    'interval': 'month',
                }
            },
        }
        r = c.put('/saas/catalog/services', json=service, headers=h)
        assert r.status_code == 200
        assert r.json()['runtime_uri'] == 'runtime://braink/tenant-agent'

        admitted = c.post('/saas/checkout-admission', json={
            'tenant_id': 'acme', 'system_id': 'braink', 'service_id': 'agent', 'plan': 'pro'
        }, headers=h)
        assert admitted.status_code == 200
        body = admitted.json()
        assert body['status'] == 'ADMITTED'
        assert body['runtime_uri'] == 'runtime://braink/tenant-agent'
        assert body['provider_plan']['plan_id'] == 'pro'
        assert body['provider_plan']['stripe_price_id'] == 'price_test_pro'

        unknown_plan = c.post('/saas/checkout-admission', json={
            'tenant_id': 'acme', 'system_id': 'braink', 'service_id': 'agent', 'plan': 'ghost'
        }, headers=h)
        assert unknown_plan.status_code == 409

        unknown_tenant = c.post('/saas/checkout-admission', json={
            'tenant_id': 'missing', 'system_id': 'braink', 'service_id': 'agent', 'plan': 'pro'
        }, headers=h)
        assert unknown_tenant.status_code == 409


def test_checkout_rejects_plan_without_provider_pricing_binding():
    with tempfile.TemporaryDirectory() as d:
        c = client(d)
        h = {'x-braink-token': 'test-token'}
        c.put('/saas/systems/braink', json={
            'system_id': 'braink', 'name': 'BRAINK', 'adapter_uri': 'adapter://braink', 'runtime_uri': 'runtime://braink/core'
        }, headers=h)
        c.put('/saas/tenants/acme', json={'tenant_id': 'acme', 'display_name': 'ACME'}, headers=h)
        c.put('/saas/catalog/services', json={
            'system_id': 'braink', 'service_id': 'agent', 'display_name': 'BRAINK Agent',
            'runtime_uri': 'runtime://braink/tenant-agent', 'plans': {'freeform': {'mode': 'subscription'}}
        }, headers=h)
        denied = c.post('/saas/checkout-admission', json={
            'tenant_id': 'acme', 'system_id': 'braink', 'service_id': 'agent', 'plan': 'freeform'
        }, headers=h)
        assert denied.status_code == 409
        assert 'provider pricing binding' in denied.json()['detail']
