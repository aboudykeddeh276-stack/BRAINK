#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

import server as data_server
from action_extensions import append_workbook_rows, commit_braink_migration
from action_runtime import (
    dispatch_casepath,
    ingest_source,
    launch_runtime,
    read_workbook_table,
    readback_runtime,
    write_proof,
)
from canonical_action_runtime import execute_canonical_action
from canonical_http import canonicalize_http_json
from runtime_control import runtime_control

PORT = 8790
ACTION_TYPE_BY_PATH = {
    "/deployment/dns/apply": "PUBLIC_DNS",
    "/deployment/tls/issue": "PUBLIC_TLS",
    "/deployment/router/apply": "ROUTER_FIREWALL",
    "/deployment/public/publish": "LIVE_PUBLIC_DEPLOYMENT",
    "/bitcoin/submit": "BITCOIN_LIVE_SUBMISSION",
    "/drive/writeback": "DRIVE_WRITEBACK",
}

class ActionHandler(data_server.Handler):
    server_version = "KEX-Unified-Action/6.1"
    def _authorized(self) -> bool:
        token = os.getenv("KEX_BEARER_TOKEN")
        if not token:return True
        return self.headers.get("Authorization", "") == f"Bearer {token}"
    def _json(self, payload: object, status: int = 200) -> None:
        route = urlparse(self.path).path if getattr(self, "path", None) else "/"
        normalized, _receipt = canonicalize_http_json(payload,direction="EGRESS",route=route)
        return super()._json(normalized, status)
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:raw={}
        else:
            try:
                payload=json.loads(self.rfile.read(length).decode("utf-8"));raw=payload if isinstance(payload,dict) else {}
            except Exception:raw={}
        route=urlparse(self.path).path if getattr(self,"path",None) else "/";authority=str(raw.get("authority",""));identity=str(raw.get("requestId","")) or None
        normalized,_receipt=canonicalize_http_json(raw,direction="INGRESS",route=route,authority=authority,identity=identity)
        if not isinstance(normalized,dict):raise TypeError("WBOS JSON ingress must resolve to a mapping")
        return normalized
    def _require_auth(self) -> bool:
        if self._authorized():return True
        self._json({"error":"unauthorized"},401);return False
    def do_GET(self) -> None:
        if not self._require_auth():return
        parsed=urlparse(self.path);parts=[p for p in parsed.path.split("/") if p]
        if len(parts)==4 and parts[0]=="workbooks" and parts[2]=="tables":
            status,payload=read_workbook_table(parts[1],parts[3]);return self._json(payload,status)
        return super().do_GET()
    def do_POST(self) -> None:
        if not self._require_auth():return
        parsed=urlparse(self.path);path=parsed.path;parts=[p for p in path.split("/") if p]
        if path in {"/activate-workbook","/workbooks/apply"}:return super().do_POST()
        payload=self._read_json()
        if path=="/actions/execute":return self._json(execute_canonical_action(payload))
        if path=="/runtime/control":return self._json(runtime_control(payload))
        if len(parts)==5 and parts[0]=="workbooks" and parts[2]=="tables" and parts[4]=="append":return self._json(append_workbook_rows(parts[1],parts[3],payload))
        if path=="/notebooklm/sources/ingest":return self._json(ingest_source(payload))
        if path=="/braink/migration/commit":return self._json(commit_braink_migration(payload))
        if path=="/casepath/dispatch":return self._json(dispatch_casepath(payload))
        if path=="/runtime/launch":return self._json(launch_runtime(payload))
        if path=="/runtime/readback":return self._json(readback_runtime(payload))
        if path=="/deployment/public/readback":
            results=[]
            for target in payload.get("targets",[]):
                result=readback_runtime({"target":target.get("url",""),"expectedText":target.get("expectedText")});result["expectedStatus"]=target.get("expectedStatus",200);result["requireTls"]=target.get("requireTls",True);results.append(result)
            ok=bool(results) and all(r.get("matched") for r in results);return self._json({"status":"VERIFIED" if ok else "FAIL","targetResults":results,"proofHash":None})
        if path=="/bitcoin/guard":
            request={"authority":payload.get("authority",""),"actionType":"BITCOIN_IBD_GUARD","target":payload.get("rpcRoute","bitcoin-rpc"),"controlRoute":payload.get("rpcRoute"),"payload":payload}
            receipt=execute_canonical_action(request);status=receipt["status"]
            return self._json({"status":status,"initialBlockDownload":True if status!="VERIFIED" else False,"peers":0,"blockHeight":0,"canMine":False,"canSubmit":False,"proofHash":receipt.get("afterHash"),"details":receipt})
        if path=="/proof/ledger/write":return self._json(write_proof(payload))
        if path in ACTION_TYPE_BY_PATH:
            action_request={"authority":payload.get("authority",""),"actionType":ACTION_TYPE_BY_PATH[path],"target":payload.get("targetDomain") or payload.get("publicIp") or payload.get("targetPath") or payload.get("rpcRoute") or path,"controlRoute":payload.get("providerRoute") or payload.get("acmeRoute") or payload.get("routerRoute") or payload.get("deploymentRoute") or payload.get("rpcRoute"),"payload":payload}
            return self._json(execute_canonical_action(action_request))
        return self._json({"error":"not_found","path":path},404)

def serve(host: str="127.0.0.1",port: int=PORT) -> None:
    data_server.append_proof("ACTION_RUNTIME_BOOT","KEX://ROOT/ACTION_RUNTIME",f"{host}:{port}")
    ThreadingHTTPServer((host,port),ActionHandler).serve_forever()
if __name__=="__main__":serve()
