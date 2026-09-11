import os, tempfile
from fastapi.testclient import TestClient

def client(tmp):
    os.environ['BRAINK_DATA_DIR']=tmp; os.environ['BRAINK_AUTH_TOKEN']='test-token'
    import importlib, braink_runtime.app as m
    importlib.reload(m)
    return TestClient(m.app)

def test_health_and_cascade():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); assert c.get('/api/health').json()['status']=='ok'; assert len(c.get('/cascade').json()['stages'])==7

def test_mutation_idempotency_and_ledger():
    with tempfile.TemporaryDirectory() as d:
        c=client(d); h={'x-braink-token':'test-token'}
        p={'action':'merge','target':'memory/fabric','payload':{'a':1},'request_id':'r1'}
        r=c.post('/actions/execute',json=p,headers=h); assert r.status_code==200
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
