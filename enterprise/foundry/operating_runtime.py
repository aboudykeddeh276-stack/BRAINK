from __future__ import annotations
from pathlib import Path
import sqlite3,time,uuid,hashlib,json
def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
class OperatingRuntime:
 def __init__(self,estate): self.estate=Path(estate).resolve(); self.receipts=[]
 def _receipt(self,foundry,action,result):
  r={"receipt_id":"OPR-"+uuid.uuid4().hex[:16],"foundry":foundry,"action":action,"result":result,"created_ns":time.time_ns()};r["root"]=root(r);self.receipts.append(r);return r
 def register_domain(self,domain,registrar='UNBOUND',owner_scope='KEDDEH_SYSTEMS'):
  db=sqlite3.connect(self.estate/'domain_dns/domains.sqlite3');i='DOM-'+uuid.uuid4().hex[:12];db.execute('INSERT INTO domains VALUES(?,?,?,?,?,?)',(i,domain,registrar,'DEFINED',owner_scope,None));db.commit();db.close();return self._receipt('domain_dns','register_domain',{'domain_id':i,'domain':domain,'state':'DEFINED'})
 def create_account(self,name):
  db=sqlite3.connect(self.estate/'sales_crm/crm.sqlite3');i='ACC-'+uuid.uuid4().hex[:12];db.execute('INSERT INTO accounts VALUES(?,?,?)',(i,name,'ACTIVE'));db.commit();db.close();return self._receipt('sales_crm','create_account',{'account_id':i,'name':name})
 def record_usage(self,customer_id,plan_id,quantity):
  db=sqlite3.connect(self.estate/'billing_revenue/billing.sqlite3');i='USE-'+uuid.uuid4().hex[:12];db.execute('INSERT INTO usage_events VALUES(?,?,?,?,?)',(i,customer_id,plan_id,float(quantity),time.time_ns()));db.commit();db.close();return self._receipt('billing_revenue','record_usage',{'usage_id':i,'quantity':float(quantity)})
 def open_ticket(self,customer_id,subject,priority='normal'):
  db=sqlite3.connect(self.estate/'customer_service/support.sqlite3');i='TKT-'+uuid.uuid4().hex[:12];db.execute('INSERT INTO tickets VALUES(?,?,?,?,?,?)',(i,customer_id,subject,priority,'OPEN',None));db.commit();db.close();return self._receipt('customer_service','open_ticket',{'ticket_id':i,'state':'OPEN'})
 def register_principal(self,principal_id,kind,name):
  db=sqlite3.connect(self.estate/'identity_iam/iam.sqlite3');db.execute('INSERT OR REPLACE INTO principals VALUES(?,?,?,?)',(principal_id,kind,name,'ACTIVE'));db.commit();db.close();return self._receipt('identity_iam','register_principal',{'principal_id':principal_id,'state':'ACTIVE'})
 def record_metric(self,subject,name,value,unit='count'):
  db=sqlite3.connect(self.estate/'observability/telemetry.sqlite3');db.execute('INSERT INTO metrics(subject,name,value,unit,observed_ns) VALUES(?,?,?,?,?)',(subject,name,float(value),unit,time.time_ns()));db.commit();db.close();return self._receipt('observability','record_metric',{'subject':subject,'name':name,'value':float(value),'unit':unit})
 def register_artifact(self,name,sha256):
  db=sqlite3.connect(self.estate/'deployment_release/releases.sqlite3');i='ART-'+uuid.uuid4().hex[:12];db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(i,name,sha256,'REGISTERED'));db.commit();db.close();return self._receipt('deployment_release','register_artifact',{'artifact_id':i,'state':'REGISTERED'})
 def audit_root(self): return root([r['root'] for r in self.receipts])
