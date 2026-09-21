#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
 env=os.environ.copy(); env.update({"KEX_SITES_DB":d+"/sites.db","KEX_SITES_STORE":d+"/objects","KEX_SITES_PUBLISH_ROOT":d+"/pub","KEX_SITES_TOKEN":"test-token"})
 p=subprocess.Popen([sys.executable,str(ROOT/"app.py"),"--port","18787"],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 try:
  for _ in range(50):
   try:
    urllib.request.urlopen("http://127.0.0.1:18787/api/health",timeout=.2); break
   except Exception: time.sleep(.05)
  def req(path,method="GET",body=None):
   data=None if body is None else json.dumps(body).encode()
   q=urllib.request.Request("http://127.0.0.1:18787"+path,data=data,method=method,headers={"Content-Type":"application/json","Authorization":"Bearer test-token"})
   with urllib.request.urlopen(q,timeout=3) as r:return json.loads(r.read())
  s=req("/api/sites","POST",{"slug":"proof-site","name":"Proof Site"}); sid=s["id"]
  s=req(f"/api/sites/{sid}/domains","POST",{"hostname":"proof.example"})
  assert s["domains"][0]["hostname"]=="proof.example"
  s=req(f"/api/sites/{sid}/versions","POST",{"message":"v1","files":{"index.html":"<h1>proof</h1>","app.js":"console.log('proof')"}})
  assert len(s["versions"])==1 and len(s["versions"][0]["source_sha256"])==64
  s=req(f"/api/sites/{sid}/deploy","POST",{"adapter":"local"})
  assert s["state"]=="DEPLOYED" and s["deployments"][0]["readback"]["index_html"] is True
  v=req("/api/ledger/verify"); assert v["ok"] and v["count"]>=4
  h=req("/api/health"); assert h["ok"] and h["ledger"]["ok"]
  print(json.dumps({"PASS":True,"site_id":sid,"ledger":v,"deployment":s["deployments"][0]},indent=2))
 finally:
  p.terminate(); p.wait(timeout=3)
