from __future__ import annotations
import json
from pathlib import Path
from enterprise.capability_deployment_runtime import CapabilityDeploymentRuntime

ROOT=Path(__file__).resolve().parents[2]
catalog=json.loads((ROOT/'enterprise/SERVICE_GENOME_CATALOG_R16.json').read_text())
bindings=json.loads((ROOT/'enterprise/R18_CAPABILITY_BINDINGS.json').read_text())
rt=CapabilityDeploymentRuntime(catalog,bindings)
packet=rt.compile('LEGAL_SERVICE','SMALL')
resident=[r for r in packet['requirements'] if r['gap_class']=='CAPABILITY_RESIDENT']
holes=[r for r in packet['requirements'] if r['gap_class']=='ADAPTER_OR_FUNCTION_REQUIRED']
assignment=next(r for r in packet['requirements'] if r['name']=='assignment')
assert len(packet['server_sets'])==18
assert len(packet['requirements'])==72
assert len(resident)==9
assert len(holes)==63
assert assignment['decision']=='REUSE'
assert assignment['state']=='BOUND'
assert assignment['implementation_ref'].endswith('braink_hr/hr_runtime.py::HRRuntime.assign')
assert packet['resident_count']==9 and packet['gap_count']==63
assert packet['deployment_root']
print(json.dumps({'status':'PASS','deployment_root':packet['deployment_root'],'server_sets':len(packet['server_sets']),'requirements':len(packet['requirements']),'resident':len(resident),'holes':len(holes),'selected_work_module':'WM://GENERAL_GOVERNANCE/assignment'},sort_keys=True))
