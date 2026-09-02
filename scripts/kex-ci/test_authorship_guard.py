import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from enterprise.governance.authorship_guard import stamp,classify,audit,ORPHAN_CLASS

valid=stamp('service://casepath/customer-file-base','deployment://r25','aboudykeddeh276-stack/BRAINK','a'*64,'2026-09-02T00:00:00Z')
inherited={'service_id':'service://casepath/workspace','deployment_id':'deployment://r25b','predecessor_id':'service://casepath/customer-file-base'}
orphan={'service_id':'service://unknown/orphan','deployment_id':'deployment://x'}
conflict={'service_id':'service://conflict','author_id':'OTHER','authorship_root':'enterprise/governance/AKD_AUTHORSHIP_ROOT.json'}
report=audit([valid,inherited,orphan,conflict])
checks={
 'direct':classify(valid).status=='AKD_AUTHORED',
 'inherited':classify(inherited,{valid['service_id']}).status=='AKD_AUTHORED_INHERITED',
 'orphan':classify(orphan).status==ORPHAN_CLASS,
 'conflict':classify(conflict).status==ORPHAN_CLASS,
 'audit_counts':report['akd_authored']==2 and report['orphaned']==2,
}
print({'checks':checks,'report':report})
raise SystemExit(0 if all(checks.values()) else 2)
