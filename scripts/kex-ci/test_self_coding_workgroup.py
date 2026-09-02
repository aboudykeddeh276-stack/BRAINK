from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from enterprise.self_coding_workgroup import AgentMember,WorkGroupRuntime,WorkModule

rt=WorkGroupRuntime()
for a in (
 AgentMember('agent://research/a','group://research',('research.project',),('research',)),
 AgentMember('agent://research/b','group://research',('research.project',),('research',)),
 AgentMember('agent://runtime/a','group://runtime',('runtime.hash',),('runtime',)),
 AgentMember('agent://evolution/a','group://evolution',('evolution.classify',),('evolution',)),
): rt.add_agent(a)

project=WorkModule('WM-RESEARCH-PROJECT-R1','Project normalized evidence fields.','research.project',{'source':'str','claim':'str','noise':'str'},{'source':'str','claim':'str'},'PROJECT_FIELDS',(
 {'input':{'source':'s','claim':'c','noise':'x'},'expected':{'source':'s','claim':'c'}},
))
r1=rt.run_group('group://research',project,{'source':'ledger','claim':'verified','noise':'ignore'})
assert len(r1)==2 and all(x.status=='EXECUTED' for x in r1)
before=len(rt.evolution_events)
r2=rt.run_group('group://research',project,{'source':'vfs','claim':'bound','noise':'ignore'})
assert len(rt.evolution_events)==before and r2[0].function_root==r1[0].function_root
hashmod=WorkModule('WM-RUNTIME-HASH-R1','Hash canonical payload.','runtime.hash',{'value':'any'},{'sha256':'str'},'HASH_PAYLOAD')
r3=rt.run_group('group://runtime',hashmod,{'value':297}); assert len(r3[0].output['sha256'])==64
classify=WorkModule('WM-EVOLUTION-CLASSIFY-R1','Classify evolution score.','evolution.classify',{'value':'float','threshold':'float'},{'classification':'str'},'CLASSIFY_THRESHOLD',(
 {'input':{'value':3,'threshold':2},'expected':{'classification':'HIGH'}},
 {'input':{'value':1,'threshold':2},'expected':{'classification':'LOW'}},
))
r4=rt.run_group('group://evolution',classify,{'value':2.97,'threshold':2.0}); assert r4[0].output['classification']=='HIGH'
assert len(rt.evolution_events)==3
print('BRAINK_SELF_CODING_WORKGROUP_PASS')
