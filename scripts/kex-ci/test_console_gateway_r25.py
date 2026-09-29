from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
import tempfile

from enterprise.market.console_gateway_r25 import AuthenticatedConsoleGateway


def request(url, token=None, method="GET", body=None):
    headers={"Content-Type":"application/json"}
    if token is not None:
        headers["Authorization"]=f"Bearer {token}"
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=3) as r:
            return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read())


def main():
    token="test-console-token"
    with tempfile.TemporaryDirectory(prefix="keddeh-console-gateway-") as tmp:
        gw=AuthenticatedConsoleGateway(Path(tmp)/"state.sqlite3",token=token)
        server=gw.handler()
        from http.server import ThreadingHTTPServer
        httpd=ThreadingHTTPServer(("127.0.0.1",0),server)
        port=httpd.server_address[1]
        t=threading.Thread(target=httpd.serve_forever,daemon=True)
        t.start()
        base=f"http://127.0.0.1:{port}"

        code,_=request(base+"/health")
        assert code==401
        code,health=request(base+"/health",token)
        assert code==200 and health["status"]=="OK"
        code,status=request(base+"/runtime/status",token)
        assert code==200 and status["status"]=="OBSERVED"
        code,caps=request(base+"/runtime/capabilities",token)
        assert "create_customer" in caps["capabilities"]

        code,executed=request(base+"/runtime/execute",token,"POST",{"operation":"create_customer","args":{"name":"Console Verification"}})
        assert code==200 and executed["status"]=="EXECUTED"
        code,receipts=request(base+"/runtime/receipts",token)
        assert code==200 and len(receipts["receipts"])>=1
        assert receipts["receipts"][0]["action"]=="create_customer"

        httpd.shutdown()
        print(json.dumps({
            "schema":"keddeh.authenticated-console-gateway.r25.test/v1",
            "status":"PASS",
            "checks":{
                "unauthenticated_rejected":True,
                "authenticated_health":True,
                "runtime_status_readback":True,
                "capability_manifest":True,
                "authenticated_mutation":True,
                "receipt_readback":True
            }
        },indent=2))


if __name__=="__main__":
    main()
