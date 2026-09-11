import os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook

def client(tmp):
    os.environ['BRAINK_DATA_DIR']=tmp; os.environ['BRAINK_AUTH_TOKEN']='test-token'
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
        audit=c.get('/saas/audit',headers=h).json()['events']
        assert any(e['event_type']=='PROVISIONING_REQUESTED' for e in audit)
