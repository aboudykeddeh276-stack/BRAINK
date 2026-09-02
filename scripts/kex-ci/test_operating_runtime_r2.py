import sys,json,sqlite3,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from enterprise.foundry.market_operating_foundries import MarketOperatingFoundry
from enterprise.foundry.operating_runtime import OperatingRuntime
with tempfile.TemporaryDirectory() as td:
 estate=Path(td)/'estate';MarketOperatingFoundry(ROOT/'enterprise/foundry/MASTER_DATASET_R1.json',estate).build_all();r=OperatingRuntime(estate)
 out=[r.register_domain('example.test'),r.create_account('Example Customer'),r.record_usage('C-1','P-1',12.5),r.open_ticket('C-1','Need help'),r.register_principal('agent://1','agent','Runtime Agent'),r.record_metric('service://1','requests',1),r.register_artifact('release.zip','a'*64)]
 checks={'seven_actions':len(out)==7,'receipts_hashed':all(len(x['root'])==64 for x in out),'audit_root':len(r.audit_root())==64,'domain_persisted':sqlite3.connect(estate/'domain_dns/domains.sqlite3').execute('select count(*) from domains').fetchone()[0]==1,'crm_persisted':sqlite3.connect(estate/'sales_crm/crm.sqlite3').execute('select count(*) from accounts').fetchone()[0]==1,'ticket_persisted':sqlite3.connect(estate/'customer_service/support.sqlite3').execute('select count(*) from tickets').fetchone()[0]==1}
 print(json.dumps({'checks':checks,'audit_root':r.audit_root()},indent=2));raise SystemExit(0 if all(checks.values()) else 2)
