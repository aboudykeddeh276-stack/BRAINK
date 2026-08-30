#!/usr/bin/env python3
"""BRAINK dynamic domain publication broadcaster."""
from __future__ import annotations
import json, socket, pathlib, time, hashlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/"deploy/BRAINK_PUBLIC_CORPORATE_RELEASE.json").read_text())
DNS_SOCKET="/tmp/keddeh-authoritative-dns.sock"
TLS_SOCKET="/tmp/keddeh-application-tls.sock"
INGRESS_SOCKET="/tmp/keddeh-public-ingress.sock"

def call(path,payload):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(15); s.connect(path)
    s.sendall((json.dumps(payload,separators=(",",":"))+"\n").encode()); buf=b""
    while not buf.endswith(b"\n"):
        x=s.recv(65536)
        if not x: break
        buf+=x
    s.close()
    if not buf: raise RuntimeError("EMPTY_PROCESS_RECEIPT:"+path)
    out=json.loads(buf.decode())
    if out.get("status") not in ("PASS","APPLIED","LIVE"): raise RuntimeError(out.get("error","PROCESS_REJECTED"))
    return out

def main():
    edges=json.load(open(sys.argv[1])) if len(sys.argv)>1 else {"manifestations":[]}
    live=[x for x in edges.get("manifestations",[]) if x.get("status") in ("LIVE","REGISTERED","ADMITTED")]
    if not live: raise SystemExit("NO_QUALIFIED_DYNAMIC_EDGE_MANIFESTATIONS")
    records=[]
    for d in MANIFEST["domains"]:
        records.append({"owner":d,"type":"A_DYNAMIC_SET","targets":[x["public_endpoint"] for x in live],"ttl":30})
    tx={"schema":"kex.braink.domain-publication.v1","domains":list(MANIFEST["domains"]),"records":records,"authority":"BRAINK_PUBLICATION_TEAM","at":time.time()}
    tx["sha256"]=hashlib.sha256(json.dumps(tx,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    receipts={"ingress":call(INGRESS_SOCKET,{"op":"ADMIT_EDGE_SET","transaction":tx}),"dns":call(DNS_SOCKET,{"op":"PUBLISH_DYNAMIC_EDGE_SET","transaction":tx}),"tls":call(TLS_SOCKET,{"op":"BIND_SNI_HOST_SET","transaction":tx})}
    out={"status":"APPLIED","transaction":tx,"receipts":receipts}
    (ROOT/"deploy/BRAINK_PUBLICATION_RECEIPT.json").write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
