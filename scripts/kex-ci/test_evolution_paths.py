import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.evolution_paths import *

T=[]
def t(n,c): T.append((n,bool(c)))
f=EvolutionFabric()
o=f.create('app://casepath','KEX://DOMAIN/CASEPATH.COM.AU',{'graph':{'/your-data.html':{'state':'BASELINE'}},'release':'CP-V50-CASEPATH-DIRECT-RUNTIME-20260828'})
u=f.dispatch(o.object_id,'KEX://DOMAIN/CASEPATH.COM.AU',{'runtime_status':'ACTIVE'})
t('update_same_identity',u['class']=='UPDATE' and u['object_id']==o.object_id)
a=f.dispatch(o.object_id,'KEX://DOMAIN/CASEPATH.COM.AU/YOUR-DATA',{'patch_id':'CP-TC-20260727-C01','graph_node':'/your-data.html','additive':True})
t('amendment_same_identity',a['class']=='AMENDMENT' and a['object_id']==o.object_id)
t('amendment_preserves_prior',f.objects[o.object_id].payload['graph']['/your-data.html']['prior']['state']=='BASELINE')
f.observe(o.object_id,'observer://public-http','PUBLIC_READBACK',{'http':200})
h=f.resolve('KEX://MEMORY/RING2/FUTURE')
t('hole_is_addressable',h['status']=='HOLE')
back=f.create('vfs://ring2','KEX://MEMORY/RING2/BOUND',{'capacity_class':'massive-array'})
f.bind_hole('KEX://MEMORY/RING2/FUTURE',back.object_id)
t('hole_binds_without_rewriting_absence',f.resolve('KEX://MEMORY/RING2/FUTURE')['status']=='RESOLVED')
e=f.dispatch(o.object_id,'KEX://DOMAIN/CASEPATH.COM.AU',{'new_class_id':'app://casepath/addressable-runtime','carrier_schema':'keddeh.runtime-carrier.v2','new_addresses':['KEX://DOMAIN/CASEPATH.COM.AU/RING1','KEX://DOMAIN/CASEPATH.COM.AU/RING2']})
t('evolution_creates_successor',e['class']=='EVOLUTION' and e['successor_id']!=o.object_id)
t('predecessor_superseded',f.objects[o.object_id].state==ObjectState.SUPERSEDED)
t('lineage_bidirectional',f.objects[e['successor_id']].predecessor_id==o.object_id and f.objects[o.object_id].successor_id==e['successor_id'])
rej=f.dispatch(o.object_id,'KEX://DOMAIN/CASEPATH.COM.AU',{'runtime_status':'STALE_WRITE'})
t('superseded_identity_rejects_update',rej['status']=='REJECTED_SUPERSEDED_IDENTITY')
c=f.carrier
t('carrier_roots_present',all(len(c[k])==64 for k in ['object_root','address_root','hole_root','observer_root','ledger_root']))
for n,c in T: print(('PASS' if c else 'FAIL')+':'+n)
raise SystemExit(0 if all(c for _,c in T) else 2)
