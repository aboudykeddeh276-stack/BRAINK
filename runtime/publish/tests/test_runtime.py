import os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook

def client(tmp):
    os.environ['BRAINK_DATA_DIR']=tmp; os.environ['BRAINK_AUTH_TOKEN']='test-token'
    os.environ['BRAINK_SAAS_ALLOW_HOST_ACTUATION']='0'
    import importlib, braink_runtime.app as m
    importlib.reload(m)
    return TestClient(m.app)

def test_health_routes_and_cascade():
    with tempfile.TemporaryDirectory() as d:
        c=client(d)
        assert c.get('/api/health').json()['status']=='ok'
        assert len(c.get('/cascade').json()['stages'])==7
        routes=c.get('/api/routes').json()['routes']
        assert '/connector/execute-action' in routes
        assert '/workbooks/append' in routes
        assert '/saas/provision' in routes
        assert '/saas/payments/verified-event' in routes
        assert '/saas/bindings' in routes
        assert '/saas/actuate-fabric' in routes

def test_mutation_idempotency_and_ledger():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        p={'action':'merge','target':'memory/fabric','payload':{'a':1},'request_id':'r1'}
        r=c.post('/connector/execute-action',json=p,headers=h); assert r.status_code==200
        r2=c.post('/actions/execute',json=p,headers=h); assert r2.json()['mutation_hash']==r.json()['mutation_hash']
        assert c.get('/runtime/memory/fabric').json()['version']==1
        assert len(c.get('/api/proof-ledger').json()['entries'])==1

def test_version_conflict():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        p={'action':'replace','target':'x','payload':{'a':1},'request_id':'r1','expected_version':0}
        assert c.post('/actions/execute',json=p,headers=h).status_code==200
        p['request_id']='r2'; p['expected_version']=0
        assert c.post('/actions/execute',json=p,headers=h).status_code==409

def test_workbook_read_append():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'book.xlsx'
        wb=Workbook(); ws=wb.active; ws.title='Runtime'; ws.append(['k','v']); wb.save(path)
        c=client(d); h={'x-braink-token':'test-token'}
        r=c.post('/workbooks/append',json={'path':str(path),'sheet':'Runtime','values':['state','active']},headers=h)
        assert r.status_code==200
        rr=c.post('/workbooks/read',json={'path':str(path),'sheet':'Runtime'},headers=h)
        assert rr.status_code==200
        assert rr.json()['rows'][-1]==['state','active']

def test_saas_node_cross_system_control_plane():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        systems=[
            ('braink','BRAINK','adapter://braink','runtime://braink/core'),
            ('kex','KEX','adapter://kex','runtime://kex/core'),
            ('casepath','CasePath','adapter://casepath','app://casepath'),
            ('claimpath','ClaimPath','adapter://claimpath','app://claimpath'),
        ]
        for sid,name,adapter,runtime in systems:
            r=c.put(f'/saas/systems/{sid}',json={'system_id':sid,'name':name,'adapter_uri':adapter,'runtime_uri':runtime},headers=h)
            assert r.status_code==200
        assert len(c.get('/saas/systems').json()['systems'])==4
        r=c.put('/saas/tenants/acme',json={'tenant_id':'acme','display_name':'ACME'},headers=h)
        assert r.status_code==200
        ent={'tenant_id':'acme','system_id':'braink','service_id':'agent','plan':'pro','limits':{'requests_per_day':1000}}
        assert c.put('/saas/entitlements',json=ent,headers=h).status_code==200
        resolved=c.get('/saas/resolve',params={'tenant_id':'acme','system_id':'braink','service_id':'agent'}).json()
        assert resolved['adapter_uri']=='adapter://braink'
        p={'tenant_id':'acme','system_id':'braink','service_id':'agent','plan':'pro','requested_by':'admin'}
        pr=c.post('/saas/provision',json=p,headers=h)
        assert pr.status_code==200
        assert pr.json()['status']=='PENDING_ACTUATION'
        plan=c.post('/saas/provision-plan',json=p,headers=h)
        assert plan.status_code==200
        assert 'RESOLVE_HOST_CONTROL' in plan.json()['stages']
        audit=c.get('/saas/audit',headers=h).json()['events']
        assert any(e['event_type']=='PROVISIONING_REQUESTED' for e in audit)

def test_verified_payment_event_entitles_and_provisions_exactly_once():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        assert c.put('/saas/systems/braink',json={
            'system_id':'braink','name':'BRAINK','adapter_uri':'adapter://braink','runtime_uri':'runtime://braink/core'
        },headers=h).status_code==200
        assert c.put('/saas/tenants/acme',json={'tenant_id':'acme','display_name':'ACME'},headers=h).status_code==200
        event={
            'provider':'stripe','event_id':'evt_001','event_type':'checkout.session.completed',
            'tenant_id':'acme','system_id':'braink','service_id':'agent','plan':'pro',
            'payment_status':'paid','payload':{'session_id':'cs_test_001'}
        }
        first=c.post('/saas/payments/verified-event',json=event,headers=h)
        assert first.status_code==200
        body=first.json()
        assert body['processing_status']=='ENTITLED_PENDING_ACTUATION'
        assert body['duplicate'] is False
        assert body['provisioning_intent_id']
        resolved=c.get('/saas/resolve',params={'tenant_id':'acme','system_id':'braink','service_id':'agent'}).json()
        assert resolved['plan']=='pro'

        replay=c.post('/saas/payments/verified-event',json=event,headers=h)
        assert replay.status_code==200
        replay_body=replay.json()
        assert replay_body['duplicate'] is True
        assert replay_body['provisioning_intent_id']==body['provisioning_intent_id']
        audit=c.get('/saas/audit',headers=h).json()['events']
        assert sum(1 for e in audit if e['event_type']=='PAYMENT_ACTIVATED')==1
        assert sum(1 for e in audit if e['event_type']=='PROVISIONING_REQUESTED')==1

def test_unpaid_payment_event_does_not_grant_access():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        assert c.put('/saas/systems/braink',json={
            'system_id':'braink','name':'BRAINK','adapter_uri':'adapter://braink','runtime_uri':'runtime://braink/core'
        },headers=h).status_code==200
        assert c.put('/saas/tenants/acme',json={'tenant_id':'acme','display_name':'ACME'},headers=h).status_code==200
        event={
            'provider':'stripe','event_id':'evt_002','event_type':'checkout.session.async_payment_failed',
            'tenant_id':'acme','system_id':'braink','service_id':'agent','plan':'pro',
            'payment_status':'failed','payload':{}
        }
        r=c.post('/saas/payments/verified-event',json=event,headers=h)
        assert r.status_code==200
        assert r.json()['processing_status']=='IGNORED_NOT_PAID'
        denied=c.get('/saas/resolve',params={'tenant_id':'acme','system_id':'braink','service_id':'agent'})
        assert denied.status_code==403

def test_saas_estate_bindings_and_fail_closed_actuation():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        bindings=c.get('/saas/bindings',headers=h)
        assert bindings.status_code==200
        body=bindings.json()
        assert body['host_actuation']['runtime_gate']=='HOST_READY + ONLINE + external carrier proof'
        assert body['payments']['public_checkout_route']=='/payments/checkout'
        assert body['public_ingress']['promotion_rule']=='public projection cannot promote resident runtime state'
        r=c.post('/saas/actuate-fabric',headers=h)
        assert r.status_code==409
        assert r.json()['detail']['reason']=='BRAINK_SAAS_ALLOW_HOST_ACTUATION_NOT_ENABLED'
