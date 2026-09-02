from __future__ import annotations
from pathlib import Path
import json,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request

ROOT=Path(__file__).resolve().parents[2]
SERVICE=ROOT/"deployment"/"r23_foundry_closure_service.py"

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0));return s.getsockname()[1]

def post(url,payload,expect=200):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=3) as r:
            assert r.status==expect,(r.status,expect);return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body=json.loads(e.read())
        assert e.code==expect,(e.code,expect,body);return body

def wait_health(base):
    for _ in range(60):
        try:
            with urllib.request.urlopen(base+"/closure/health",timeout=.5) as r:
                body=json.loads(r.read())
                if body.get("status")=="PASS" and body.get("customer_access")=="BOUND":return body
        except Exception:pass
        time.sleep(.05)
    raise RuntimeError("SERVICE_NOT_READY")

with tempfile.TemporaryDirectory(prefix="braink-r24-portal-") as td:
    state=Path(td)/"state.json";port=free_port();base=f"http://127.0.0.1:{port}"
    proc=subprocess.Popen([sys.executable,str(SERVICE),"--state",str(state),"--host","127.0.0.1","--port",str(port)],cwd=ROOT)
    try:
        wait_health(base)
        customer_id="customer://portal/1";file_id="customer-file://portal/1";token="opaque-session-token-1"
        created=post(base+"/closure/operate",{"action":"customer.lifecycle.create","payload":{"file_id":file_id,"customer_id":customer_id,"consent":{"privacy":True}}})
        assert created["status"]=="EXECUTED"
        bound=post(base+"/portal/session/bind",{"session_token":token,"profile":{"sub":"oauth-sub-1","email":"portal@example.invalid"},"customer_id":customer_id,"scopes":["customer_file:read"],"ttl_ns":1000000,"now_ns":100})
        assert bound["status"]=="EXECUTED"
        read=post(base+"/portal/customer-file/read",{"session_token":token,"file_id":file_id,"now_ns":200})
        assert read["file_id"]==file_id and read["customer_id"]==customer_id and len(read["access_receipt_root"])==64
        denied=post(base+"/portal/customer-file/read",{"session_token":"wrong-token","file_id":file_id,"now_ns":200},403)
        assert denied["status"]=="REJECTED" and "SESSION_NOT_FOUND" in denied["reason"]
        other="customer-file://portal/2"
        post(base+"/closure/operate",{"action":"customer.lifecycle.create","payload":{"file_id":other,"customer_id":"customer://portal/2","consent":{"privacy":True}}})
        denied=post(base+"/portal/customer-file/read",{"session_token":token,"file_id":other,"now_ns":200},403)
        assert "CUSTOMER_OWNERSHIP_MISMATCH" in denied["reason"]
        revoked=post(base+"/portal/session/revoke",{"session_token":token,"reason":"test-revoke","now_ns":300})
        assert revoked["status"]=="EXECUTED"
        denied=post(base+"/portal/customer-file/read",{"session_token":token,"file_id":file_id,"now_ns":400},403)
        assert "SESSION_NOT_ACTIVE" in denied["reason"]
    finally:
        proc.terminate();proc.wait(timeout=5)

    raw=state.read_text()
    assert token not in raw and "portal@example.invalid" in raw
    before=json.loads(raw);before_root=before["state_root"]
    port2=free_port();base2=f"http://127.0.0.1:{port2}"
    proc2=subprocess.Popen([sys.executable,str(SERVICE),"--state",str(state),"--host","127.0.0.1","--port",str(port2)],cwd=ROOT)
    try:
        wait_health(base2)
        denied=post(base2+"/portal/customer-file/read",{"session_token":token,"file_id":file_id,"now_ns":500},403)
        assert "SESSION_NOT_ACTIVE" in denied["reason"]
    finally:
        proc2.terminate();proc2.wait(timeout=5)
    after=json.loads(state.read_text())
    assert before_root!=after["state_root"]
    assert after["customer_sessions"]
    assert after["customer_access_audit"]

print("R24_CUSTOMER_PORTAL_HTTP_BINDING_PASS")
