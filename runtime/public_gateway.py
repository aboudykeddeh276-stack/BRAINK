#!/usr/bin/env python3
"""
BRAINK public rail gateway.
Sites never hold Google/Stripe secret material. They call dedicated local rail
processes over Unix sockets and receive bounded results.
"""
from __future__ import annotations
import json, os, socket, http.server, urllib.parse, base64

OAUTH_SOCKET = os.environ.get("BRAINK_OAUTH_SOCKET", "/tmp/braink-oauth.sock")
STRIPE_SOCKET = os.environ.get("BRAINK_STRIPE_SOCKET", "/tmp/braink-stripe.sock")

def rail_call(path: str, payload: dict) -> dict:
    body=(json.dumps(payload,separators=(",",":"))+"\n").encode()
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        s.settimeout(10)
        s.connect(path)
        s.sendall(body)
        buf=b""
        while not buf.endswith(b"\n"):
            x=s.recv(65536)
            if not x: break
            buf+=x
        if not buf: raise RuntimeError("EMPTY_RAIL_RESPONSE")
        out=json.loads(buf.decode())
        if out.get("status") not in ("PASS","OK","AUTHORIZED","CREATED"):
            raise RuntimeError(out.get("error","RAIL_REJECTED"))
        return out
    finally:
        s.close()

class Handler(http.server.BaseHTTPRequestHandler):
    server_version="BRAINKPublic/1"
    def json(self, code, obj):
        b=json.dumps(obj,separators=(",",":")).encode()
        self.send_response(code); self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u=urllib.parse.urlsplit(self.path)
        q=urllib.parse.parse_qs(u.query)
        if u.path=="/health":
            return self.json(200,{"status":"PASS","runtime":"runtime://braink/public-gateway/1"})
        if u.path=="/auth/google/start":
            domain=q.get("domain",["braink.com.au"])[0]
            try:
                r=rail_call(OAUTH_SOCKET,{"op":"AUTHORIZE_URL","domain":domain,"return_to":q.get("return_to",["/"])[0]})
                self.send_response(302); self.send_header("Location",r["authorization_url"]); self.end_headers()
            except Exception as e: self.json(503,{"status":"BLOCKED","component":"BRAINK_GOOGLE_OAUTH_RAIL","error":str(e)})
            return
        if u.path=="/auth/google/callback":
            try:
                r=rail_call(OAUTH_SOCKET,{"op":"CALLBACK","query":{k:v[0] for k,v in q.items()}})
                return self.json(200,{"status":"PASS","session":r.get("session"),"profile":r.get("profile")})
            except Exception as e: return self.json(401,{"status":"REJECTED","component":"BRAINK_GOOGLE_OAUTH_RAIL","error":str(e)})
        return self.json(404,{"status":"NOT_FOUND"})

    def do_POST(self):
        n=int(self.headers.get("Content-Length","0")); raw=self.rfile.read(n)
        ctype=self.headers.get("Content-Type","")
        try:
            data=json.loads(raw or b"{}") if "json" in ctype else dict(urllib.parse.parse_qsl(raw.decode()))
        except Exception: data={}
        if self.path=="/payments/checkout":
            try:
                r=rail_call(STRIPE_SOCKET,{"op":"CREATE_CHECKOUT","request":data})
                return self.json(200,{"status":"PASS","checkout_url":r["checkout_url"],"session_id":r.get("session_id")})
            except Exception as e: return self.json(503,{"status":"BLOCKED","component":"BRAINK_STRIPE_PAYMENT_RAIL","error":str(e)})
        if self.path=="/payments/stripe/webhook":
            try:
                r=rail_call(STRIPE_SOCKET,{"op":"WEBHOOK","payload_b64":base64.b64encode(raw).decode(),"stripe_signature":self.headers.get("Stripe-Signature","")})
                return self.json(200,{"status":"PASS","event":r.get("event")})
            except Exception as e: return self.json(400,{"status":"REJECTED","component":"BRAINK_STRIPE_PAYMENT_RAIL","error":str(e)})
        return self.json(404,{"status":"NOT_FOUND"})

if __name__=="__main__":
    host=os.environ.get("BRAINK_BIND","127.0.0.1")
    port=int(os.environ.get("BRAINK_PORT","8799"))
    http.server.ThreadingHTTPServer((host,port),Handler).serve_forever()
