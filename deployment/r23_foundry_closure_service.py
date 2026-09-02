from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from enterprise.foundry_closure_r23 import DurableStore,HRSupervisionRuntime,CustomerFileLifecycle,ResearchPromotionGate,PublicationRuntime

def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
class Runtime:
    def __init__(self,state):
        self.store=DurableStore(state);self.hr=HRSupervisionRuntime(self.store);self.customers=CustomerFileLifecycle(self.store);self.research=ResearchPromotionGate(self.store);self.publishing=PublicationRuntime(self.store)
    def operate(self,a,p):
        d={
          "hr.lease.acquire":lambda:self.hr.acquire(p["lease_id"],p["supervisor_id"],p["subject_id"],int(p["ttl_ns"]),p.get("now_ns")),
          "hr.lease.replace_rehydrate":lambda:self.hr.expire_and_replace(p["subject_id"],p["lease_id"],p["supervisor_id"],int(p["ttl_ns"]),int(p["now_ns"])),
          "customer.lifecycle.create":lambda:self.customers.create(p["file_id"],p["customer_id"],p.get("consent",{})),
          "customer.lifecycle.transition":lambda:self.customers.transition(p["file_id"],p["target"],p.get("reason","")),
          "customer.lifecycle.event":lambda:self.customers.append_event(p["file_id"],p["kind"],p.get("payload",{})),
          "research.promotion.evaluate":lambda:self.research.evaluate(p["research_id"],p.get("claims",[]),p.get("sources",[]),p.get("replays",[]),p.get("independent_verifier")),
          "publishing.stage":lambda:self.publishing.stage(p["release_id"],p.get("artifacts",[]),p["frontage_id"],p.get("approval",{})),
          "publishing.project_internal":lambda:self.publishing.publish_internal(p["release_id"],p["projection_ref"]),
          "domain.public_activation.request":lambda:self.publishing.request_public_activation(p["release_id"],p["domain"],p.get("dns_changes",[]),p.get("tls_required",True),None),
        }
        if a not in d:raise KeyError("UNKNOWN_R23_ACTION")
        r=d[a]();return {**r.__dict__,"receipt_root":r.receipt_root}
class Handler(BaseHTTPRequestHandler):
    runtime=None
    def reply(self,c,o):
        b=canonical(o);self.send_response(c);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def body(self):
        n=int(self.headers.get("Content-Length","0") or 0);return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        if urlparse(self.path).path=="/closure/health":return self.reply(200,{"status":"PASS","runtime":"BRAINK_R23","generation":self.runtime.store.state["generation"]})
        if urlparse(self.path).path=="/closure/state":return self.reply(200,self.runtime.store.state)
        return self.reply(404,{"status":"NOT_FOUND"})
    def do_POST(self):
        if urlparse(self.path).path!="/closure/operate":return self.reply(404,{"status":"NOT_FOUND"})
        try:
            b=self.body();return self.reply(200,self.runtime.operate(b["action"],b.get("payload",{})))
        except (KeyError,ValueError,RuntimeError) as e:return self.reply(400,{"status":"REJECTED","reason":str(e)})
    def log_message(self,*args):pass

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--state",required=True);ap.add_argument("--host",default=os.getenv("BRAINK_R23_HOST","127.0.0.1"));ap.add_argument("--port",type=int,default=int(os.getenv("BRAINK_R23_PORT","8800")));a=ap.parse_args();Handler.runtime=Runtime(a.state);ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=="__main__":main()
