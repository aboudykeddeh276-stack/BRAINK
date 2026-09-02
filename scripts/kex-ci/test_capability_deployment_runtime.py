from __future__ import annotations
import json
from pathlib import Path
from enterprise.capability_deployment_runtime import CapabilityDeploymentRuntime

ROOT=Path(__file__).resolve().parents[2]
catalog=json.loads((ROOT/'enterprise/SERVICE_GENOME_CATALOG_R16.json').read_text())
rt=CapabilityDeploymentRuntime(catalog)
for cap,ref in {
 'agent_dispatch':'enterprise/braink_sector_federation.py',
 'continuation':'enterprise/continuation_runtime.py',
 'artifact':'enterprise/addressability_fabric.py',
 'lineage':'enterprise/backing_migration.py',
 'receipt':'enterprise/audit_observability.py',
 'reconciliation':'enterprise/observer_policy.py',
 'process':'enterprise/autonomous_evolution_runtime.py',
 'telemetry':'enterprise/audit_observability.py',
}.items(): rt.bind(cap,ref)
packet=rt.compile('LEGAL_SERVICE','SMALL')
assert len(packet['server_sets'])==18
assert any(r['gap_class']=='CAPABILITY_RESIDENT' for r in packet['requirements'])
assert any(r['gap_class']=='ADAPTER_OR_FUNCTION_REQUIRED' for r in packet['requirements'])
assert packet['deployment_root']
print(json.dumps({'status':'PASS','deployment_root':packet['deployment_root'],'server_sets':len(packet['server_sets']),'requirements':len(packet['requirements'])},sort_keys=True))
