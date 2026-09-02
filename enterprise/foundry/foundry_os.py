from __future__ import annotations
from pathlib import Path
import hashlib,json,sqlite3,time,html

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(v): return hashlib.sha256(canon(v).encode()).hexdigest()

class FoundryOS:
    def __init__(self,master_dataset,output_root):
        self.master_path=Path(master_dataset).resolve(); self.master=json.loads(self.master_path.read_text()); self.master_root=sha(self.master)
        self.output_root=Path(output_root).resolve(); self.output_root.mkdir(parents=True,exist_ok=True)
    def build_all(self,estate_name='KEDDEH_SYSTEMS'):
        return {kind:self.build(kind,estate_name) for kind in self.master['foundry_classes']}
    def build(self,kind,name):
        if kind not in self.master['foundry_classes']: raise KeyError(kind)
        p=self.output_root/kind; p.mkdir(parents=True,exist_ok=True); getattr(self,f'_build_{kind}')(p,name)
        manifest=self._index(p,kind,name); (p/'FOUNDRY_MANIFEST.json').write_text(json.dumps(manifest,indent=2)); return manifest
    def _dataset_ref(self):
        return {'canonical_path':str(self.master_path),'root':self.master_root,'sector_count':len(self.master['sector_products']['products']),'function_count':sum(len(x['functions']) for x in self.master['sector_products']['products'].values())}
    def _write(self,p,name,obj):
        q=p/name; q.write_text(obj if isinstance(obj,str) else json.dumps(obj,indent=2)); return q
    def _index(self,p,kind,name):
        files=[]
        for q in sorted(p.rglob('*')):
            if q.is_file() and q.name!='FOUNDRY_MANIFEST.json': files.append({'path':str(q.relative_to(p)),'bytes':q.stat().st_size,'sha256':hashlib.sha256(q.read_bytes()).hexdigest()})
        return {'schema':'braink.foundry.output.v1','foundry':kind,'estate':name,'master_dataset':self._dataset_ref(),'files':files,'created_ns':time.time_ns()}
    def _all_services(self):
        return [{'sector':sector,'function':fn,'adapters':cfg['adapters'],'controls':cfg['controls'],'billable_units':cfg['billable_units']} for sector,cfg in self.master['sector_products']['products'].items() for fn in cfg['functions']]
    def _build_business_enterprise_structure(self,p,name):
        services=self._all_services(); teams=[{'team':g,'supervision':'recursive','work_scope':'bounded'} for g in self.master['hr_groups']]
        self._write(p,'enterprise_registry.json',{'estate':name,'dataset':self._dataset_ref(),'sectors':list(self.master['sector_products']['products'])})
        self._write(p,'service_matrix.json',{'services':services}); self._write(p,'team_matrix.json',{'teams':teams})
        self._write(p,'operating_graph.json',{'nodes':[name]+[x['team'] for x in teams]+list(self.master['sector_products']['products']),'edges':[{'from':name,'to':x['team'],'type':'SUPERVISES'} for x in teams]})
    def _build_server(self,p,name):
        self._write(p,'server_registry.json',{'dataset':self._dataset_ref(),'services':self._all_services()})
        server_code="""from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer\nimport json,os\nBASE=os.path.dirname(__file__)\nSERVICES=json.load(open(os.path.join(BASE,'server_registry.json')))\nclass H(BaseHTTPRequestHandler):\n def _send(self,obj,code=200):\n  b=json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)\n def do_GET(self):\n  if self.path=='/health': return self._send({'status':'ok','service_count':len(SERVICES['services'])})\n  if self.path=='/services': return self._send(SERVICES)\n  return self._send({'error':'not_found'},404)\nif __name__=='__main__': ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','18990'))),H).serve_forever()\n"""
        self._write(p,'server_runtime.py',server_code); self._write(p,'host_bindings.json',{'logical_host':'KEDDEH_SERVER_FABRIC','bind':'127.0.0.1','port':18990,'public_projection':'UNBOUND'}); self._write(p,'health_contract.json',{'endpoint':'/health','service_index':'/services'})
    def _build_agentics(self,p,name):
        services=self._all_services(); groups=self.master['hr_groups']; work=[{'work_module_id':'WM-'+sha({'sector':s['sector'],'function':s['function']})[:20],'sector':s['sector'],'function':s['function'],'groups':groups,'state':'DEFINED'} for s in services]
        self._write(p,'agent_registry.json',{'groups':groups,'dataset':self._dataset_ref()}); self._write(p,'work_module_register.json',{'work_modules':work}); self._write(p,'supervision_graph.json',{'rule':'every supervisor may itself be supervised; ring depth is derived topology'})
        self._write(p,'agent_runtime.py',"""import json,os\nBASE=os.path.dirname(__file__)\nGROUPS=json.load(open(os.path.join(BASE,'agent_registry.json')))['groups']\ndef dispatch(work_module):\n return [{'group':g,'supervisor':f\"supervisor://{work_module['work_module_id']}/{g}\",'work_module_id':work_module['work_module_id'],'state':'ASSIGNED'} for g in GROUPS]\n""")
    def _build_hci(self,p,name):
        sectors=self.master['sector_products']['products']; cards=''.join(f'<section><h2>{html.escape(k)}</h2><p>{len(v["functions"])} functions</p></section>' for k,v in sectors.items())
        page=f"<!doctype html><meta charset=utf-8><title>{html.escape(name)} Control Surface</title><style>body{{font-family:system-ui;max-width:1200px;margin:auto;padding:2rem}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}}section{{border:1px solid #888;padding:1rem;border-radius:12px}}</style><h1>{html.escape(name)} Control Surface</h1><nav>Services · Workspaces · Files · Agents · Servers · Research · Publishing · Customers</nav><main>{cards}</main>"
        self._write(p,'ui_dataset.json',{'dataset':self._dataset_ref(),'navigation':['Services','Workspaces','Files','Agents','Servers','Research','Publishing','Customers'],'sectors':sectors}); self._write(p,'index.html',page)
    def _build_landing_page(self,p,name):
        sectors=self.master['sector_products']['products']; sections=''.join(f'<section><h2>{html.escape(k)}</h2><ul>'+''.join(f'<li>{html.escape(fn)}</li>' for fn in v['functions'])+'</ul></section>' for k,v in sectors.items())
        self._write(p,'site_dataset.json',{'dataset':self._dataset_ref(),'products':sectors}); self._write(p,'index.html',f'<!doctype html><meta charset=utf-8><title>{html.escape(name)}</title><h1>{html.escape(name)}</h1><p>Service estate generated from the canonical BRAINK sector registry.</p>{sections}'); self._write(p,'domain_routes.json',{'domains':[],'routes':[{'path':f'/services/{s}/{fn}','sector':s,'function':fn} for s,v in sectors.items() for fn in v['functions']]})
    def _build_workspace(self,p,name):
        db=sqlite3.connect(p/'workspace.sqlite3'); db.executescript('CREATE TABLE workspaces(id TEXT PRIMARY KEY,name TEXT,state TEXT);CREATE TABLE tasks(id TEXT PRIMARY KEY,workspace_id TEXT,title TEXT,state TEXT);CREATE TABLE artifacts(id TEXT PRIMARY KEY,workspace_id TEXT,path TEXT,sha256 TEXT);'); db.execute('INSERT INTO workspaces VALUES(?,?,?)',('WS-ROOT',name,'ACTIVE')); db.commit(); db.close(); self._write(p,'workspace_registry.json',{'dataset':self._dataset_ref(),'root_workspace':'WS-ROOT','team_groups':self.master['hr_groups']})
    def _build_file_system(self,p,name):
        db=sqlite3.connect(p/'vfs.sqlite3'); db.executescript('CREATE TABLE objects(logical_address TEXT PRIMARY KEY,backing TEXT,object_hash TEXT,state TEXT);CREATE TABLE lineage(seq INTEGER PRIMARY KEY AUTOINCREMENT,logical_address TEXT,event TEXT,root TEXT);'); db.commit(); db.close(); mounts=[{'logical':'VFS://BRAINK','backing':'./braink','mode':'rw'},{'logical':'VFS://CUSTOMERS','backing':'./customers','mode':'rw'},{'logical':'VFS://RESEARCH','backing':'./research','mode':'rw'},{'logical':'VFS://PUBLISHING','backing':'./publishing','mode':'rw'}]; self._write(p,'mount_table.json',{'dataset':self._dataset_ref(),'mounts':mounts}); self._write(p,'retention_policy.json',{'immutable_receipts':True,'lineage_required':True,'default_retention_days':2555})
    def _build_customer_file_base(self,p,name):
        db=sqlite3.connect(p/'customer_files.sqlite3'); db.executescript('CREATE TABLE customers(id TEXT PRIMARY KEY,display_name TEXT,state TEXT);CREATE TABLE files(id TEXT PRIMARY KEY,customer_id TEXT,name TEXT,logical_address TEXT,sha256 TEXT,state TEXT);CREATE TABLE tasks(id TEXT PRIMARY KEY,customer_id TEXT,title TEXT,state TEXT);CREATE TABLE messages(id TEXT PRIMARY KEY,customer_id TEXT,body TEXT,created_ns INTEGER);CREATE TABLE audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,customer_id TEXT,event TEXT,receipt_root TEXT,created_ns INTEGER);'); db.commit(); db.close(); self._write(p,'customer_portal.html','<!doctype html><meta charset=utf-8><title>Customer File Base</title><h1>Customer File Base</h1><nav>Files · Tasks · Messages · Exports · Audit</nav><p>Runtime-backed customer file software. Data is stored in customer_files.sqlite3.</p>'); self._write(p,'permissions.json',{'customer':['read','upload','export','message'],'staff':['read','write','assign','message'],'admin':['*']}); self._write(p,'retention.json',{'legal_hold_supported':True,'default_days':2555})
    def _build_publishing_process_research(self,p,name):
        db=sqlite3.connect(p/'research_publish.sqlite3'); db.executescript('CREATE TABLE research(id TEXT PRIMARY KEY,topic TEXT,state TEXT,source_root TEXT);CREATE TABLE processes(id TEXT PRIMARY KEY,name TEXT,state TEXT);CREATE TABLE publications(id TEXT PRIMARY KEY,title TEXT,state TEXT,proof_root TEXT);CREATE TABLE approvals(id TEXT PRIMARY KEY,publication_id TEXT,role TEXT,state TEXT);'); db.commit(); db.close(); self._write(p,'publication_pipeline.json',{'stages':['research','draft','technical_review','proof','approval','publish','observe','reconcile'],'proof_required':True}); self._write(p,'process_mastery.json',{'state_machine':self.master['process_state_machine'],'runtime_primitive':self.master['shared_runtime_primitive']})
