from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import argparse, json, hashlib, os, time, sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.foundry_operations_r22 import FoundaryOperationsRuntime


def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def root(v): return hashlib.sha256(canonical(v)).hexdigest()


class Store:
    def __init__(self,path,foundary_path=None,operations_state=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {"generation":0,"deployments":{},"foundary_compositions":{}}
        self.state.setdefault("foundary_compositions",{})
        fp = Path(foundary_path) if foundary_path else ROOT/"enterprise"/"FOUNDRY_REGISTRY_R21.json"
        self.foundary_registry=json.loads(fp.read_text("utf-8")) if fp.exists() else {"schema":"braink.foundary-registry.r21/v1","foundaries":{}}
        op_state = Path(operations_state) if operations_state else self.path.parent/"foundary_operations_r22.json"
        self.operations = FoundaryOperationsRuntime(op_state)

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
            "schema":"braink.foundary-runtime-composition.r22/v1",
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

    def operate(self, action, p):
        op=self.operations
        dispatch={
            "undertaking.create": lambda: op.business.create_undertaking(p["undertaking_id"],p["purpose"],p.get("service_genomes",[]),p.get("business_units",[]),p.get("market_targets",[])),
            "team.register": lambda: op.hr.register_team(p["team_id"],p["undertaking_id"],p.get("roles",[]),p.get("capabilities",[]),p.get("authority_roots",[])),
            "server_room.materialize": lambda: op.servers.materialize_room(p["room_id"],p["undertaking_id"],p["server_sets"],p.get("dependencies",{})),
            "workspace.create": lambda: op.workspace.create(p["workspace_id"],p["undertaking_id"],p["owner_team"]),
            "file.write": lambda: op.files.write(p["address"],p.get("payload",{}),p.get("workspace_id")),
            "customer_file.create": lambda: op.customers.create_customer_file(p["customer_id"],p["undertaking_id"],p.get("consent",{}),p.get("service_state",{})),
            "frontage.register": lambda: op.frontages.register_frontage(p["frontage_id"],p["undertaking_id"],p["hostname"],p.get("routes",{}),p.get("mesh_targets",[])),
            "hci.register": lambda: op.hci.register_surface(p["surface_id"],p["undertaking_id"],p.get("controls",[]),p.get("accessibility_contract",{})),
            "landing.manufacture": lambda: op.landing.manufacture(p["page_id"],p["undertaking_id"],p["frontage_id"],p["proposition"],p.get("sections",[]),p.get("conversion_actions",[])),
            "svg.register": lambda: op.svg.register_svg(p["svg_id"],p["undertaking_id"],p.get("graph_nodes",[]),p.get("graph_edges",[]),p.get("metadata",{})),
            "research.register": lambda: op.research.register_case_study(p["research_id"],p["undertaking_id"],p.get("claims",[]),p.get("sources",[]),p.get("reproducibility",{})),
            "agentics.dispatch": lambda: op.agentics.dispatch(p["task_id"],p["undertaking_id"],p["team_id"],p["work_module"],p["target_foundary"]),
            "software.register": lambda: op.software.register_product(p["product_id"],p["undertaking_id"],p.get("entrypoints",[]),p.get("tests",[]),p.get("packaging",{}),p.get("runtime_contract",{})),
            "publishing.stage": lambda: op.publishing.stage_release(p["release_id"],p["undertaking_id"],p.get("artifacts",[]),p["frontage_id"],p.get("approvals",[])),
        }
        if action not in dispatch:
            raise KeyError("UNKNOWN_FOUNDRY_ACTION")
        receipt=dispatch[action]()
        return {**receipt.__dict__,"receipt_root":receipt.receipt_root}


class Handler(BaseHTTPRequestHandler):
    store=None
    def reply(self,code,obj):
        b=canonical(obj); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def read_json(self):
        n=int(self.headers.get("Content-Length","0") or "0")
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        p=urlparse(self.path); q=parse_qs(p.query)
        if p.path=="/health": return self.reply(200,{"status":"PASS","runtime":"BRAINK_R22","generation":self.store.state["generation"],"foundary_count":len(self.store.foundary_registry.get("foundaries",{})),"foundary_operation_generation":self.store.operations.store.state["generation"]})
        if p.path=="/state": return self.reply(200,self.store.state)
        if p.path=="/operations-state": return self.reply(200,self.store.operations.store.state)
        if p.path=="/process-summary": return self.reply(200,self.store.operations.process.process_summary())
        if p.path=="/compile": return self.reply(200,self.store.compile(q.get("undertaking",["LEGAL_SERVICE"])[0]))
        if p.path=="/foundaries": return self.reply(200,{"schema":self.store.foundary_registry.get("schema"),"foundaries":sorted(self.store.foundary_registry.get("foundaries",{}))})
        if p.path=="/foundary":
            name=q.get("name",[None])[0]
            if not name or name not in self.store.foundary_registry.get("foundaries",{}): return self.reply(404,{"status":"FOUNDARY_NOT_FOUND","name":name})
            return self.reply(200,self.store.foundary_address(name))
        if p.path=="/compose-foundaries":
            undertaking=q.get("undertaking",["LEGAL_SERVICE"])[0]
            names=[n for n in q.get("names",[""])[0].split(",") if n]
            missing=[n for n in names if n not in self.store.foundary_registry.get("foundaries",{})]
            if missing: return self.reply(400,{"status":"REJECTED","missing_foundaries":missing})
            return self.reply(200,self.store.compose_foundaries(undertaking,names))
        return self.reply(404,{"status":"NOT_FOUND"})
    def do_POST(self):
        p=urlparse(self.path)
        if p.path != "/operate": return self.reply(404,{"status":"NOT_FOUND"})
        try:
            body=self.read_json(); return self.reply(200,self.store.operate(body["action"],body.get("payload",{})))
        except (KeyError,ValueError) as exc:
            return self.reply(400,{"status":"REJECTED","reason":str(exc)})
    def log_message(self,*args): pass


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--state",required=True); ap.add_argument("--operations-state",default=os.getenv("BRAINK_FOUNDRY_OPERATIONS_STATE")); ap.add_argument("--foundaries",default=os.getenv("BRAINK_FOUNDARY_REGISTRY")); ap.add_argument("--host",default=os.getenv("BRAINK_HOST","127.0.0.1")); ap.add_argument("--port",type=int,default=int(os.getenv("BRAINK_PORT","8799"))); a=ap.parse_args()
    Handler.store=Store(a.state,a.foundaries,a.operations_state); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=="__main__": main()
