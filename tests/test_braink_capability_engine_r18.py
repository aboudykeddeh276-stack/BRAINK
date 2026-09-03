from pathlib import Path
import base64, json, tempfile
from braink_capability_engine_r18 import CapabilityEngine, CapabilityError, mutating_allowed
TMP=Path(tempfile.mkdtemp(prefix='braink-cap-r18-')); MASTER=b'M'*64; NOW=2_000_000_000
PAYLOAD={'amount':7,'target':'alpha','nested':{'x':[1,2,3]}}
def must_fail(fn,code):
    try: fn()
    except CapabilityError as e:
        assert e.code==code,(e.code,code); return
    raise AssertionError('expected '+code)
def split(tok):
    a,b=tok.split('.'); body=json.loads(base64.urlsafe_b64decode(a+'='*(-len(a)%4))); return a,b,body
def reenc(body):
    raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode(); return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
results=[]
eng=CapabilityEngine(MASTER,TMP/'a.sqlite3',max_ttl_seconds=120,clock_skew_seconds=0)
t=eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); eng.verify(t,principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW); results.append('valid_one_shot')
t=eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=10,now=NOW); must_fail(lambda:eng.verify(t,principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW+11),'expired'); results.append('expiry')
t=eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); must_fail(lambda:eng.verify(t,principal='alice',product_id='prodA',operation='write',payload={**PAYLOAD,'amount':8},now=NOW),'payload_mismatch'); results.append('payload_tamper')
t=eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); must_fail(lambda:eng.verify(t,principal='alice',product_id='prodB',operation='write',payload=PAYLOAD,now=NOW),'product_mismatch'); results.append('product_scope')
t=eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); must_fail(lambda:eng.verify(t,principal='alice',product_id='prodA',operation='delete',payload=PAYLOAD,now=NOW),'operation_mismatch'); results.append('operation_scope')
t=eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); a,b,body=split(t); body['principal']='bob'; forged=reenc(body)+'.'+b; must_fail(lambda:eng.verify(forged,principal='bob',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW),'bad_signature'); results.append('principal_relabel')
a,b,body=split(eng.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW)); sig=bytearray(base64.urlsafe_b64decode(b+'='*(-len(b)%4))); sig[0]^=1; bad=a+'.'+base64.urlsafe_b64encode(bytes(sig)).rstrip(b'=').decode(); must_fail(lambda:eng.verify(bad,principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW),'bad_signature'); results.append('signature_flip')
must_fail(lambda:eng.verify('not-a-token',principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW),'malformed_token'); results.append('malformed')
eng2=CapabilityEngine(MASTER,TMP/'replay.sqlite3',max_ttl_seconds=120,clock_skew_seconds=0); t=eng2.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); ok=replay=0
for _ in range(10000):
    try: eng2.verify(t,principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW); ok+=1
    except CapabilityError as e: assert e.code=='replay'; replay+=1
assert (ok,replay)==(1,9999),(ok,replay); results.append('replay_10000')
db=TMP/'restart.sqlite3'; e1=CapabilityEngine(MASTER,db,max_ttl_seconds=120,clock_skew_seconds=0); t=e1.issue('alice','prodA','write',PAYLOAD,ttl_seconds=30,now=NOW); e1.verify(t,principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW); e2=CapabilityEngine(MASTER,db,max_ttl_seconds=120,clock_skew_seconds=0); must_fail(lambda:e2.verify(t,principal='alice',product_id='prodA',operation='write',payload=PAYLOAD,now=NOW),'replay'); results.append('persistent_replay')
e4=CapabilityEngine(MASTER,TMP/'gate.sqlite3',max_ttl_seconds=120,clock_skew_seconds=0); t=e4.issue('alice','billing','invoice.create',{'id':1},ttl_seconds=30,now=NOW); allowed,reason=mutating_allowed(e4,t,principal='alice',product_id='billing',operation='invoice.create',payload={'id':1},now=NOW); assert allowed and reason=='authorized'; results.append('gate_exact_binding')
t=e4.issue('alice','billing','invoice.create',{'id':2},ttl_seconds=30,now=NOW); allowed,reason=mutating_allowed(e4,t,principal='alice',product_id='billing',operation='invoice.delete',payload={'id':2},now=NOW); assert not allowed and reason=='operation_mismatch'; results.append('gate_changed_request_rejected')
print(json.dumps({'status':'PASS','tests':results,'count':len(results)},indent=2))
