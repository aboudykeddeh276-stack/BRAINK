import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
R16=ROOT/'federation'/'R16'
sys.path.insert(0,str(R16))
from sector_activation_runtime import SectorActivationRuntime
activation=json.loads((R16/'ACTIVE_SECTOR_BINDINGS_R16.json').read_text())
rt=SectorActivationRuntime(activation)
for sid in ['HR_SERVER_SET','AGENTIC_AI_SERVER_SET','MEMORY_SERVER_SET','MAILING_INTEGRATION_SERVER_SET','DEPLOYMENT_SERVER_SET']:
    rt.register_server_handler(sid,lambda packet,sid=sid:{'status':'DISPATCHED','handler':sid,'packet_function':packet['function']})
assert len(activation['bindings'])==12
for b in activation['bindings']:
    fn=b['market_functions'][0]
    out=rt.execute(b['sector_id'],fn,{'activation_test':True})
    assert out['status']=='DISPATCHED',(b['sector_id'],out)
    assert out['work']['hr_team']==b['hr_team']
    assert set(out['work']['server_sets'])==set(b['server_sets'])
assert rt.execute('AI_CLOUD_INFRA','not-a-function',{})['status']=='FUNCTION_NOT_REGISTERED'
summary=rt.activation_summary()
assert summary['active_bindings']==12
assert summary['work_receipts']==12
assert len(summary['receipt_root'])==64
print('PASS:R16-12-sector-activation')
print(summary)
