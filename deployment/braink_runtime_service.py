from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import argparse, json, hashlib, os, time


def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def root(v): return hashlib.sha256(canonical(v)).hexdigest()


class Store:
    def __init__(self,path,foundary_path=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {"generation":0,"deployments":{},"foundary_compositions":{}}
        self.state.setdefault("foundary_compositions",{})
        fp = Path(foundary_path) if foundary_path else Path(__file__).resolve().parents[1]/"enterprise"/"FOUNDRY_REGISTRY_R21.json"
        self.foundary_registry=json.loads(fp.read_text("utf-8")) if fp.exists() else {"schema":"braink.foundary-registry.r21/v1","foundaries":{}}

    def persist(self):
        tmp=self.path.with_suffix(".tmp"); tmp.write_bytes(canonical(self.state)); os.replace(tmp,self.path)

    def compile(self,undertaking):
        body={"undertaking":undertaking,"compiled_ns":time.time_ns()}; body["deployment_root"]=root(body)
        self.state["generation"]+=1; self.state["deployments"][undertaking]=body; self.persist(); return body

    def foundary_address(self,name):
        f=self.foundary_registry["foundaries"][name]
        body={"name":name,**f}; body["foundary_root"]=root(body)
        body["counts"]={"process_domains":len(f["process_domains"]),"server_sets":len(f["server_sets"]),"agent_teams":len(f["agent_teams"]),"data_classes":len(f["data_classes"]),"repositories":len(f["repositories"]),"virtual_roots":len(f["virtual_roots"])}
        return body

    def compose_foundaries(self,undertaking,names):
        selected=[self.foundary_address(n) for n in names]
        composition={
            "schema":"braink.foundary-runtime-composition.r21/v1",
            "undertaking":undertaking,
            "foundaries":names,
            "foundary_roots":[x["foundary_root"] for x in selected],
            "process_domains":sorted({v for x in selected for v in x["process_domains"]}),
            "server_sets":sorted({v for x in selected for v in x["server_sets"]}),
            "agent_teams":sorted({v for x in selected for v in x["agent_teams"]}),
            "data_classes":sorted({v for x in selected for v in x["data_classes"]}),
            "repositories":sorted({v for x in selected for v in x["repositories"]}),
            "virtual_roots":sorted({v for x in selected for v in x["virtual_roots"]}),
            "created_ns":time.time_ns()
        }
        composition["composition_root"]=root(composition)
        self.state["generation"]+=1
        self.state["foundary_compositions"][undertaking]=composition
        self.persist()
        return composition


class Handler(BaseHTTPRequestHandler):
    store=None
    def reply(self,code,obj):
        b=canonical(obj); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p=urlparse(self.path); q=parse_qs(p.query)
        if p.path=="/health": return self.reply(200,{"status":"PASS","runtime":"BRAINK_R21","generation":self.store.state["generation"],"foundary_count":len(self.store.foundary_registry.get("foundaries",{}))})
        if p.path=="/state": return self.reply(200,self.store.state)
        if p.path=="/compile": return self.reply(200,self.store.compile(q.get("undertaking",["LEGAL_SERVICE"])[0]))
        if p.path=="/foundaries":
            return self.reply(200,{"schema":self.store.foundary_registry.get("schema"),"foundaries":sorted(self.store.foundary_registry.get("foundaries",{}))})
        if p.path=="/foundary":
            name=q.get("name",[None])[0]
            if not name or name not in self.store.foundary_registry.get("foundaries",{}): return self.reply(404,{"status":"FOUNDARY_NOT_FOUND","name":name})
            return self.reply(200,self.store.foundary_address(name))
        if p.path=="/compose-foundaries":
            undertaking=q.get("undertaking",["LEGAL_SERVICE"])[0]
            raw=q.get("names",[""])[0]
            names=[n for n in raw.split(",") if n]
            missing=[n for n in names if n not in self.store.foundary_registry.get("foundaries",{})]
            if missing: return self.reply(400,{"status":"REJECTED","missing_foundaries":missing})
            return self.reply(200,self.store.compose_foundaries(undertaking,names))
        return self.reply(404,{"status":"NOT_FOUND"})
    def log_message(self,*args): pass


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--state",required=True); ap.add_argument("--foundaries",default=os.getenv("BRAINK_FOUNDARY_REGISTRY")); ap.add_argument("--host",default=os.getenv("BRAINK_HOST","127.0.0.1")); ap.add_argument("--port",type=int,default=int(os.getenv("BRAINK_PORT","8799"))); a=ap.parse_args()
    Handler.store=Store(a.state,a.foundaries); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=="__main__": main()
