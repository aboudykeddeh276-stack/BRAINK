import tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.substrate_adapters import *
from enterprise.self_addressing_runtime import *

T=[]
def t(n,c,d=None):T.append((n,bool(c),d))

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    rt=SelfAddressingRuntime(td/'carrier.json')
    backing=f"sqlite://{td/'ring2.sqlite3'}#objects"
    w=rt.route('KEX://BRAINK/MEMORY/CURRENT',backing,'WRITE',{'generation':1})
    t('auto_bind_sqlite',w['status']=='COMMITTED',w)
    r=rt.route('KEX://BRAINK/MEMORY/CURRENT',backing,'READ')
    t('read_after_bind',r['status']=='READ' and r['value']['generation']==1,r)
    fback=f"file://{td/'casepath.json'}"
    w2=rt.route('KEX://DOMAIN/CASEPATH/STATE',fback,'WRITE',{'patch':'CP-TC-20260727-C01'})
    t('auto_bind_file',w2['status']=='COMMITTED',w2)
    bad=rt.route('KEX://REMOTE/FUTURE','unknown://future','WRITE',{'x':1})
    t('unresolved_stays_hole',bad['status']=='HOLE_REMAINS',bad)
    t('observer_enqueues_repair',any(c.process_id=='process://runtime/reconcile' for c in rt.continuations.queue.values()))
    rt.register_reconciler(lambda payload:{'status':'DONE','subject':payload['subject'],'decision':'DEFER_UNTIL_ADAPTER_AVAILABLE'})
    c=rt.continuation_tick()
    t('continuation_executes',c['status']=='COMPLETED',c)
    cp=rt.checkpoint()
    t('carrier_checkpoint',cp['status']=='CHECKPOINTED' and Path(cp['path']).exists(),cp)
    successor=SelfAddressingRuntime(td/'carrier.json')
    restored=successor.restore()
    successor.register_reconciler(lambda payload:{'status':'DONE'})
    t('carrier_restore',restored['status']=='RESTORED' and successor.tick_count==rt.tick_count,restored)
    rr=successor.route('KEX://BRAINK/MEMORY/CURRENT',backing,'READ')
    t('restored_binding_operates',rr['status']=='READ' and rr['value']['generation']==1,rr)
    desc=successor.registry.discover(backing,'WRITE')
    t('capability_discovery',desc['status']=='RESOLVED' and desc['adapter_id']=='adapter://sqlite/json',desc)

for n,c,d in T: print(('PASS' if c else 'FAIL')+':'+n)
raise SystemExit(0 if all(c for _,c,_ in T) else 2)
