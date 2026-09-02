import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.governance.authorship_audit import audit
r=audit(ROOT)
checks={
 'deployments_seen':r['summary']['total']>=6,
 'no_orphans':r['summary']['orphaned']==0,
 'canonical_root_present':any(x.get('service_id')=='KEDDEH_SYSTEMS_RUNTIME_ACTIVE_R1' and x['classification']=='AKD_AUTHORED' for x in r['results']),
 'r25_lineage_present':any(x.get('service_id')=='KEDDEH_SYSTEMS_R25_LIVE_SERVICE_DEPLOYMENT' and x['classification']=='AKD_AUTHORED_INHERITED' for x in r['results'])
}
print(json.dumps({'checks':checks,'audit':r},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
