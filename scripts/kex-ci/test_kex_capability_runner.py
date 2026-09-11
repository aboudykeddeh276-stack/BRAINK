#!/usr/bin/env python3
import base64, hashlib, hmac, importlib.util, json, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/'modules'/'kex_wbos'/'capability_runner.py'
spec=importlib.util.spec_from_file_location('capability_runner',MOD); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Resolver:
    def resolve(self, capability):
        assert capability==m.PAYMENT_CAPABILITY
        return {'secret_key':'sk_test_INTERNAL_ONLY','webhook_secret':'whsec_INTERNAL_ONLY'}

def transport(secret,path,form):
    assert secret=='sk_test_INTERNAL_ONLY'; assert path=='/v1/checkout/sessions'
    assert form['metadata[admission_id]']=='adm_test_001'
    assert form['metadata[tenant_id]']=='TENANT-1'; assert form['metadata[system_id]']=='braink'
    assert form['metadata[service_id]']=='svc'; assert form['metadata[plan]']=='pro'
    return {'id':'cs_test_123','url':'https://checkout.stripe.com/c/pay/cs_test_123'}

with tempfile.TemporaryDirectory() as td:
    runner=m.KEXCapabilityRunner(resolver=Resolver(),stripe_transport=transport,authority_check=lambda r:r.get('caller')=='service://braink/stripe-payment-rail',ledger_path=Path(td)/'ledger.jsonl')
    base={'op':'EXECUTE_CAPABILITY','capability':m.PAYMENT_CAPABILITY,'result_policy':m.RESULT_POLICY,'caller':'service://braink/stripe-payment-rail'}
    assert runner.execute({**base,'caller':'service://evil','operation':'STRIPE_CREATE_CHECKOUT','payload':{}})['status']=='REJECTED'
    incomplete=runner.execute({**base,'operation':'STRIPE_CREATE_CHECKOUT','payload':{'tenant_id':'TENANT-1','system_id':'braink','service_id':'svc','plan':'price_missing_admission'}})
    assert incomplete['status']=='REJECTED' and incomplete['error']=='STRIPE_SAAS_ROUTE_REQUIRED'
    checkout=runner.execute({**base,'operation':'STRIPE_CREATE_CHECKOUT','payload':{'admission_id':'adm_test_001','domain':'braink.com.au','tenant_id':'TENANT-1','system_id':'braink','service_id':'svc','plan':{'plan_id':'pro','unit_amount':1000,'currency':'aud','mode':'payment'}}})
    assert checkout['status']=='PASS' and checkout['result']['session_id']=='cs_test_123'
    raw=json.dumps({'id':'evt_1','type':'checkout.session.completed','created':1,'livemode':False,'data':{'object':{'id':'cs_test_123','customer':'cus_1','payment_status':'paid','metadata':{'admission_id':'adm_test_001','tenant_id':'TENANT-1','system_id':'braink','service_id':'svc','plan':'pro'},'secret':'MUST_NOT_ESCAPE'}}},separators=(',',':')).encode()
    ts=int(time.time()); sig=hmac.new(b'whsec_INTERNAL_ONLY',str(ts).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    webhook=runner.execute({**base,'operation':'STRIPE_VERIFY_WEBHOOK','payload':{'payload_b64':base64.b64encode(raw).decode(),'stripe_signature':f't={ts},v1={sig}'}})
    assert webhook['status']=='PASS'
    rendered=json.dumps(webhook); assert 'INTERNAL_ONLY' not in rendered and 'MUST_NOT_ESCAPE' not in rendered
    metadata=webhook['result']['event']['data']['object']['metadata']
    assert metadata=={'admission_id':'adm_test_001','tenant_id':'TENANT-1','system_id':'braink','service_id':'svc','plan':'pro'}
    assert webhook['result']['event']['data']['object']['payment_status']=='paid'
    ledger=(Path(td)/'ledger.jsonl').read_text(); assert 'INTERNAL_ONLY' not in ledger
print('KEX_CAPABILITY_RUNNER_PASS')
