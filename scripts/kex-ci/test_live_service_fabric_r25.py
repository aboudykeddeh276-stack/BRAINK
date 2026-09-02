import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from enterprise.market.live_service_fabric_r25 import LiveMarketServiceFabric

db=ROOT/'runtime/test_r25.sqlite3'
if db.exists():db.unlink()
s=LiveMarketServiceFabric(db)
bindings=s.bind_observed_infrastructure()
instances=[
 s.create_service_instance('casepath','customer_file_base'),
 s.create_service_instance('casepath','workspaces'),
 s.create_service_instance('casepath','publishing'),
 s.create_service_instance('braink','research_illlm'),
 s.create_service_instance('keddeh-systems','server_rooms'),
 s.create_service_instance('casepath','customer_services_mail'),
]
hole=s.create_service_instance('casepath','payment_provider')
m=s.live_metrics()
checks={
 '11_observed_resources':len(bindings)==11 and m['external_resources']==11,
 'six_live_instances':m['service_instances']==6,
 'all_instances_active':all(x['state']=='ACTIVE' for x in instances),
 'payment_fail_closed':hole['state']=='HELD_RESOURCE_HOLE',
 'receipts_emitted':m['receipts']>=17,
 'live_root':len(m['live_state_root'])==64
}
print(json.dumps({'checks':checks,'metrics':m},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
