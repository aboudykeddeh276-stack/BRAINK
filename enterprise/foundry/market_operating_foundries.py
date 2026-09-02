from pathlib import Path
import json,sqlite3,hashlib,time,html
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(v): return hashlib.sha256(canon(v).encode()).hexdigest()
class MarketOperatingFoundry:
 NAMES=("domain_dns","frontage_website_fleet","sales_crm","billing_revenue","customer_service","identity_iam","admin_console","observability","deployment_release","trust_centre")
 def __init__(self,master_path,root,identity=None,parent_identity=None,continuation='READY'):
  self.master_path=Path(master_path).resolve(); self.master=json.loads(self.master_path.read_text())
  self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True); self.master_root=sha(self.master)
  self.identity=identity or ('computer://foundry/'+sha({'root':str(self.root),'master_root':self.master_root})[:20])
  self.parent_identity=parent_identity
  self.continuation=continuation
 @classmethod
 def rehydrate(cls,manifest_path,master_path=None):
  manifest_path=Path(manifest_path).resolve(); m=json.loads(manifest_path.read_text())
  resolved_master=Path(master_path).resolve() if master_path else Path(m['master_locator']).resolve()
  runtime_root=manifest_path.parent.parent
  return cls(resolved_master,runtime_root,identity=m['runtime_identity'],parent_identity=m.get('parent_identity'),continuation=m.get('continuation','READY'))
 def functions(self):
  return [{"sector":s,"function":fn,"adapters":cfg["adapters"],"controls":cfg["controls"],"billable_units":cfg["billable_units"]}
          for s,cfg in self.master["sector_products"]["products"].items() for fn in cfg["functions"]]
 def _db(self,path,schema):
  c=sqlite3.connect(path);c.executescript(schema);c.commit();c.close()
 def _manifest(self,p,name):
  fs=[{"path":str(q.relative_to(p)),"bytes":q.stat().st_size,"sha256":hashlib.sha256(q.read_bytes()).hexdigest()}
      for q in sorted(p.rglob("*")) if q.is_file() and q.name!="FOUNDRY_MANIFEST.json"]
  m={"schema":"braink.operating-foundry.output.v2","foundry":name,"master_root":self.master_root,
     "runtime_identity":self.identity,"parent_identity":self.parent_identity,"continuation":self.continuation,
     "constructor_ref":"enterprise/foundry/market_operating_foundries.py:MarketOperatingFoundry",
     "master_locator":str(self.master_path),
     "sector_count":len(self.master["sector_products"]["products"]),"function_count":len(self.functions()),"files":fs,"created_ns":time.time_ns()}
  m["manifest_root"]=sha({k:m[k] for k in m if k!="manifest_root"})
  (p/"FOUNDRY_MANIFEST.json").write_text(json.dumps(m,indent=2)); return m
 def build_all(self): return {n:self.build(n) for n in self.NAMES}
 def instantiate_child(self,carrier_foundry,child_foundry,child_name,continuation='READY'):
  carrier=self.root/carrier_foundry
  if not carrier.exists(): self.build(carrier_foundry)
  child_root=carrier/'descendants'/child_name
  child_identity=self.identity+'/'+carrier_foundry+'/descendant/'+child_name
  child=MarketOperatingFoundry(self.master_path,child_root,identity=child_identity,parent_identity=self.identity,continuation=continuation)
  manifest=child.build(child_foundry)
  return {'child_root':str(child_root.resolve()),'child_identity':child_identity,'manifest':manifest}
 def build(self,name):
  p=self.root/name;p.mkdir(parents=True,exist_ok=True);getattr(self,"_build_"+name)(p);return self._manifest(p,name)
 def _build_domain_dns(self,p):
  self._db(p/"domains.sqlite3","CREATE TABLE IF NOT EXISTS domains(id TEXT PRIMARY KEY,domain TEXT UNIQUE,registrar TEXT,state TEXT,owner_scope TEXT,renewal_at TEXT);CREATE TABLE IF NOT EXISTS dns_records(id TEXT PRIMARY KEY,domain_id TEXT,type TEXT,name TEXT,value TEXT,ttl INTEGER,state TEXT);CREATE TABLE IF NOT EXISTS certificates(id TEXT PRIMARY KEY,domain_id TEXT,issuer TEXT,not_before TEXT,not_after TEXT,state TEXT);CREATE TABLE IF NOT EXISTS routes(id TEXT PRIMARY KEY,domain_id TEXT,path TEXT,target TEXT,state TEXT);CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT,domain_id TEXT,kind TEXT,value TEXT,observed_ns INTEGER);")
  (p/"DOMAIN_FUNCTION_REGISTER.json").write_text(json.dumps({"functions":["register_domain","set_dns_record","remove_dns_record","bind_route","issue_certificate_request","record_certificate","check_domain_state","record_observation","plan_failover","record_renewal"],"public_projection_is_observer":True},indent=2))
  (p/"domain_control.py").write_text("def define_route(domain,path,target): return {'domain':domain,'path':path,'target':target,'state':'DEFINED'}\n")
 def _build_frontage_website_fleet(self,p):
  self._db(p/"websites.sqlite3","CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY,brand TEXT,domain TEXT,state TEXT);CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY,site_id TEXT,route TEXT,title TEXT,state TEXT);CREATE TABLE IF NOT EXISTS offers(id TEXT PRIMARY KEY,site_id TEXT,name TEXT,price_text TEXT,state TEXT);CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,site_id TEXT,release_root TEXT,state TEXT);")
  sv=self.functions();cards=''.join(f"<li>{html.escape(x['sector'])} / {html.escape(x['function'])}</li>" for x in sv)
  (p/"fleet_index.html").write_text("<!doctype html><meta charset=utf-8><h1>Keddeh Systems Service Fleet</h1><ul>"+cards+"</ul>")
  (p/"routes.json").write_text(json.dumps({"routes":[{"path":f"/services/{x['sector']}/{x['function']}","sector":x["sector"],"function":x["function"]} for x in sv]},indent=2))
 def _build_sales_crm(self,p):
  self._db(p/"crm.sqlite3","CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,name TEXT,state TEXT);CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,account_id TEXT,name TEXT,email TEXT,state TEXT);CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY,contact_id TEXT,source TEXT,state TEXT);CREATE TABLE IF NOT EXISTS opportunities(id TEXT PRIMARY KEY,account_id TEXT,name TEXT,value REAL,stage TEXT);CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY,opportunity_id TEXT,total REAL,state TEXT);CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY AUTOINCREMENT,subject_id TEXT,kind TEXT,note TEXT,created_ns INTEGER);")
 def _build_billing_revenue(self,p):
  self._db(p/"billing.sqlite3","CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,name TEXT,state TEXT);CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,name TEXT,unit TEXT,unit_price REAL,state TEXT);CREATE TABLE IF NOT EXISTS subscriptions(id TEXT PRIMARY KEY,customer_id TEXT,plan_id TEXT,state TEXT);CREATE TABLE IF NOT EXISTS usage_events(id TEXT PRIMARY KEY,customer_id TEXT,plan_id TEXT,quantity REAL,created_ns INTEGER);CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY,customer_id TEXT,total REAL,state TEXT);CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY,invoice_id TEXT,amount REAL,state TEXT);CREATE TABLE IF NOT EXISTS ledger(seq INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,subject TEXT,amount REAL,receipt_root TEXT);")
 def _build_customer_service(self,p):
  self._db(p/"support.sqlite3","CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY,customer_id TEXT,subject TEXT,priority TEXT,state TEXT,assigned_to TEXT);CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,ticket_id TEXT,author TEXT,body TEXT,created_ns INTEGER);CREATE TABLE IF NOT EXISTS sla(id TEXT PRIMARY KEY,ticket_id TEXT,response_due_ns INTEGER,resolution_due_ns INTEGER,state TEXT);CREATE TABLE IF NOT EXISTS escalations(id TEXT PRIMARY KEY,ticket_id TEXT,reason TEXT,state TEXT);CREATE TABLE IF NOT EXISTS knowledge(id TEXT PRIMARY KEY,title TEXT,body TEXT,state TEXT);")
 def _build_identity_iam(self,p):
  self._db(p/"iam.sqlite3","CREATE TABLE IF NOT EXISTS principals(id TEXT PRIMARY KEY,type TEXT,name TEXT,state TEXT);CREATE TABLE IF NOT EXISTS roles(id TEXT PRIMARY KEY,name TEXT);CREATE TABLE IF NOT EXISTS grants(principal_id TEXT,role_id TEXT,scope TEXT,state TEXT,PRIMARY KEY(principal_id,role_id,scope));CREATE TABLE IF NOT EXISTS leases(id TEXT PRIMARY KEY,principal_id TEXT,scope TEXT,epoch INTEGER,state TEXT,expires_ns INTEGER);CREATE TABLE IF NOT EXISTS revocations(id INTEGER PRIMARY KEY AUTOINCREMENT,principal_id TEXT,reason TEXT,created_ns INTEGER);")
  (p/"authorization.py").write_text("def authorize(grants,scope): return any(g.get('state')=='ACTIVE' and g.get('scope') in (scope,'ALL') for g in grants)\ndef fence_epoch(epoch): return epoch+1\n")
 def _build_admin_console(self,p):
  nav=["Organisations","Customers","Users","Agents","Services","Domains","Sites","Billing","Support","Deployments","Proof","Workspaces","Files","Policies","Incidents"]
  (p/"admin_state.json").write_text(json.dumps({"navigation":nav,"master_root":self.master_root},indent=2))
  (p/"index.html").write_text("<!doctype html><meta charset=utf-8><h1>BRAINK Admin Console</h1><nav>"+" · ".join(nav)+"</nav>")
 def _build_observability(self,p):
  self._db(p/"telemetry.sqlite3","CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,subject TEXT,name TEXT,value REAL,unit TEXT,observed_ns INTEGER);CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,subject TEXT,kind TEXT,payload TEXT,observed_ns INTEGER);CREATE TABLE IF NOT EXISTS health(subject TEXT PRIMARY KEY,state TEXT,detail TEXT,observed_ns INTEGER);CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,subject TEXT,severity TEXT,state TEXT,created_ns INTEGER);")
  (p/"functions.json").write_text(json.dumps({"functions":["record_metric","record_event","set_health","open_alert","close_alert","query_metrics","query_events","calculate_slo","calculate_error_budget","export_observability_receipt"]},indent=2))
 def _build_deployment_release(self,p):
  self._db(p/"releases.sqlite3","CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,name TEXT,sha256 TEXT,state TEXT);CREATE TABLE IF NOT EXISTS builds(id TEXT PRIMARY KEY,artifact_id TEXT,state TEXT,proof_root TEXT);CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,build_id TEXT,channel TEXT,state TEXT,created_ns INTEGER);CREATE TABLE IF NOT EXISTS deployments(id TEXT PRIMARY KEY,release_id TEXT,target TEXT,state TEXT,receipt_root TEXT);CREATE TABLE IF NOT EXISTS rollbacks(id TEXT PRIMARY KEY,deployment_id TEXT,reason TEXT,state TEXT);")
  (p/"release_gate.py").write_text("def promotable(test_pass,proof_root,approvals): return bool(test_pass and proof_root and approvals)\n")
 def _build_trust_centre(self,p):
  self._db(p/"trust.sqlite3","CREATE TABLE IF NOT EXISTS controls(id TEXT PRIMARY KEY,name TEXT,state TEXT,evidence_root TEXT);CREATE TABLE IF NOT EXISTS policies(id TEXT PRIMARY KEY,title TEXT,state TEXT,version TEXT);CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,title TEXT,severity TEXT,state TEXT,public_summary TEXT);CREATE TABLE IF NOT EXISTS disclosures(id TEXT PRIMARY KEY,title TEXT,body TEXT,state TEXT);CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,subject TEXT,kind TEXT,root TEXT,state TEXT);")
  (p/"index.html").write_text("<!doctype html><meta charset=utf-8><h1>Keddeh Systems Trust Centre</h1><nav>Security · Privacy · Availability · Policies · Incidents · Data Handling · Evidence</nav>")
