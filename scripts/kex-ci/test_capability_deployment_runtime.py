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
scope=next(r for r in packet['requirements'] if r['name']=='scope')
identity=next(r for r in packet['requirements'] if r['name']=='identity')
role=next(r for r in packet['requirements'] if r['name']=='role')
assert len(packet['server_sets'])==18
assert len(packet['requirements'])==72
assert len(resident)==12
assert len(holes)==60
assert assignment['decision']=='REUSE' and assignment['state']=='BOUND'
assert assignment['implementation_ref'].endswith('braink_hr/hr_runtime.py::HRRuntime.assign')
assert scope['decision']=='REUSE' and scope['state']=='BOUND'
assert scope['implementation_ref'].endswith('runtime://keddeh/identity/check_scope')
assert identity['decision']=='REUSE' and identity['state']=='VERIFIED'
assert identity['implementation_ref'].endswith('hr_runtime.py::HRAssignment.agent_id')
assert role['decision']=='REUSE' and role['state']=='VERIFIED'
assert role['implementation_ref'].endswith('hr_runtime.py::HRAssignment.roles')
assert packet['resident_count']==12 and packet['gap_count']==60
assert packet['deployment_root']
print(json.dumps({'status':'PASS','deployment_root':packet['deployment_root'],'server_sets':len(packet['server_sets']),'requirements':len(packet['requirements']),'resident':len(resident),'holes':len(holes),'selected_work_module':'WM://GENERAL_GOVERNANCE/scope','reconciled_resident':['identity','role','scope']},sort_keys=True))
