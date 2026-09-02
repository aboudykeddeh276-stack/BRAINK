import json,sys,sqlite3,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from enterprise.foundry.market_operating_foundries import MarketOperatingFoundry
estate=ROOT/'runtime/KEDDEH_SYSTEMS_FOUNDRY_ESTATE_R2'
if estate.exists(): shutil.rmtree(estate)
f=MarketOperatingFoundry(ROOT/'enterprise/foundry/MASTER_DATASET_R1.json',estate)
m=f.build_all();m2=f.build_all()
checks={'ten_new_foundries':len(m)==10,'idempotent_rebuild':len(m2)==10,'preserve_12_sectors':len(f.master['sector_products']['products'])==12,'preserve_120_functions':len(f.functions())==120,'all_same_master_root':all(x['master_root']==f.master_root for x in m2.values()),'all_manifests_120':all(x['function_count']==120 for x in m2.values()),'frontage_routes_120':len(json.loads((estate/'frontage_website_fleet/routes.json').read_text())['routes'])==120}
for rel,n in [('domain_dns/domains.sqlite3',5),('sales_crm/crm.sqlite3',6),('billing_revenue/billing.sqlite3',7),('customer_service/support.sqlite3',5),('identity_iam/iam.sqlite3',5),('observability/telemetry.sqlite3',4),('deployment_release/releases.sqlite3',5),('trust_centre/trust.sqlite3',5)]:
 c=sqlite3.connect(estate/rel);checks[rel]=c.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]>=n;c.close()
print(json.dumps({'checks':checks,'master_root':f.master_root},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
