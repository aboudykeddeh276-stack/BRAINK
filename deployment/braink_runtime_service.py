from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import argparse, json, hashlib, os, time

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
def root(v): return hashlib.sha256(canonical(v)).hexdigest()

class Store:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {"generation":0,"deployments":{}}
    def compile(self,undertaking):
        body={"undertaking":undertaking,"compiled_ns":time.time_ns()}; body["deployment_root"]=root(body)
        self.state["generation"]+=1; self.state["deployments"][undertaking]=body
        tmp=self.path.with_suffix(".tmp"); tmp.write_bytes(canonical(self.state)); os.replace(tmp,self.path)
        return body

class Handler(BaseHTTPRequestHandler):
    store=None
    def reply(self,code,obj):
        b=canonical(obj); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=="/health": return self.reply(200,{"status":"PASS","generation":self.store.state["generation"]})
        if p.path=="/state": return self.reply(200,self.store.state)
        if p.path=="/compile":
            q=parse_qs(p.query); return self.reply(200,self.store.compile(q.get("undertaking",["LEGAL_SERVICE"])[0]))
        return self.reply(404,{"status":"NOT_FOUND"})
    def log_message(self,*args): pass

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--state",required=True); ap.add_argument("--host",default=os.getenv("BRAINK_HOST","127.0.0.1")); ap.add_argument("--port",type=int,default=int(os.getenv("BRAINK_PORT","8799"))); a=ap.parse_args()
    Handler.store=Store(a.state); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=="__main__": main()
