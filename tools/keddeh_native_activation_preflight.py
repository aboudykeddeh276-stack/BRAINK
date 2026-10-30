#!/usr/bin/env python3
"""Read-only KEDDEH native-carrier activation preflight.

Distinguishes an HTTP page, reachable MCP transport, authenticated MCP
response, and native BOOT_SUBSTRATE execution proof. Never promotes a mere
HTTP 200 or a dispatch receipt to proof of native execution.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

def probe(url, method="GET", payload=None, token=None):
    headers = {"Accept": "application/json, text/event-stream", "User-Agent": "KEDDEH-Native-Activation-Preflight/1"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read(65536)
            return {"status":response.status,"content_type":response.headers.get("Content-Type",""),"body":body.decode("utf-8","replace")}
    except urllib.error.HTTPError as e:
        return {"status":e.code,"content_type":e.headers.get("Content-Type",""),"body":e.read(512).decode("utf-8","replace")}
    except Exception as e:
        return {"status":None,"error":type(e).__name__+ ": "+str(e)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--origin",default="https://www.keddeh.com")
    p.add_argument("--node-readback",help="path to independently obtained JSON self-host readback; never fabricated")
    a=p.parse_args()
    origin=a.origin.rstrip("/")
    token=os.environ.get("KEDDEH_MCP_BEARER_TOKEN")
    storage=probe(origin+"/apps/storage")
    mcp=probe(origin+"/api/mcp","POST",{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"keddeh-native-preflight","version":"1.0"}}},token)
    ctype=mcp.get("content_type","").lower()
    body=mcp.get("body","")
    transport_supported=mcp.get("status")==200 and ("json" in ctype or "event-stream" in ctype) and ("jsonrpc" in body or "event:" in body or "data:" in body)
    result={"origin":origin,"storage_http_status":storage.get("status"),"mcp_http_status":mcp.get("status"),
      "mcp_content_type":mcp.get("content_type"),"mcp_transport_observed":transport_supported,
      "authenticated_mcp_execution":False,"native_node_observed":False,"durable_boot_receipt_observed":False,
      "boundary":"MCP transport reachability is not native process execution"}
    if a.node_readback:
        try:
            with open(a.node_readback,encoding="utf-8") as f: state=json.load(f)
            nodes=state.get("nodes",[])
            result["native_node_observed"]=any(n.get("state")=="ONLINE" or n.get("online") is True for n in nodes)
            result["durable_boot_receipt_observed"]=bool(state.get("currentBoot",{}).get("durable_receipt")) if isinstance(state.get("currentBoot"),dict) else False
        except (OSError,ValueError,TypeError) as e:
            result["readback_error"]=type(e).__name__
    print(json.dumps(result,sort_keys=True))
    return 0 if result["mcp_transport_observed"] and result["native_node_observed"] and result["durable_boot_receipt_observed"] else 2

if __name__=="__main__":
    sys.exit(main())
