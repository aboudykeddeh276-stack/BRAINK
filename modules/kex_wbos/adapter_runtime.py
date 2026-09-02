import subprocess,urllib.request,hashlib
class HTTPAdapter:
 def probe(self):return {"status":"PASS"}
 def execute(self,r):
  with urllib.request.urlopen(r["url"],timeout=r.get("timeout",5)) as x:
   b=x.read();return {"status":"PASS" if x.status==r.get("expected_status",200) else "FAIL","http_status":x.status,"sha256":hashlib.sha256(b).hexdigest()}
class LocalGitAdapter:
 def probe(self):return {"status":"PASS" if subprocess.run(["git","--version"],capture_output=True).returncode==0 else "FAIL"}
 def execute(self,r):
  p=subprocess.run(["git",*r["args"]],cwd=r["repo"],capture_output=True,text=True,timeout=r.get("timeout",30))
  return {"status":"PASS" if p.returncode==0 else "FAIL","returncode":p.returncode,"stdout":p.stdout[-4000:],"stderr":p.stderr[-4000:]}
ADAPTERS={"HTTP":HTTPAdapter(),"LOCAL_GIT":LocalGitAdapter()}
def execute_adapter(name,request):
 a=ADAPTERS.get(name)
 if not a:return {"status":"BLOCKED","reason":"ADAPTER_NOT_BOUND","adapter":name}
 q=a.probe()
 if q["status"]!="PASS":return {"status":"BLOCKED","reason":"ADAPTER_NOT_QUALIFIED","probe":q}
 out=a.execute(request);return {"adapter":name,"result":out,"readback":out}
