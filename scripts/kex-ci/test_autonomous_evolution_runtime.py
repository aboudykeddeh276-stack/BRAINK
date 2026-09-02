import tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.autonomous_evolution_runtime import AutonomousEvolutionRuntime

T=[]
def t(n,c): T.append((n,bool(c)))
with tempfile.TemporaryDirectory() as td:
    td=Path(td); rt=AutonomousEvolutionRuntime(td/'carrier.json')
    rt.register_reconciler(lambda p:{'status':'DONE','decision':p['decision']['action'],'subject':p['subject']})
    case=rt.evolution.create('app://casepath','KEX://DOMAIN/CASEPATH.COM.AU',{'graph':{'/your-data.html':{'state':'BASELINE'}}})
    sql=f"sqlite://{td/'r2.sqlite3'}#objects"; file=f"file://{td/'r2_migrated.json'}"
    t('source_write',rt.route('KEX://MEMORY/MIGRATION/IDENTITY',sql,'WRITE',{'generation':1})['status']=='COMMITTED')
    t('migration_committed',rt.migrate_backing('KEX://MEMORY/MIGRATION/IDENTITY',file)['status']=='COMMITTED')
    t('ring1_identity_preserved',rt.route('KEX://MEMORY/MIGRATION/IDENTITY',file,'READ')['value']['generation']==1)
    sig={'subject':case.object_id,'kind':'HASH_MISMATCH','payload':{'expected':'a','observed':'b'}}
    t('critical_signal_quarantines',rt.mutate(case.object_id,'KEX://DOMAIN/CASEPATH.COM.AU/YOUR-DATA',{'patch_id':'CP-TC-20260727-C01','graph_node':'/your-data.html','additive':True},[sig])['status']=='QUARANTINE')
    a=rt.mutate(case.object_id,'KEX://DOMAIN/CASEPATH.COM.AU/YOUR-DATA',{'patch_id':'CP-TC-20260727-C01','graph_node':'/your-data.html','additive':True})
    t('clean_patch_amends',a['status']=='DISPATCHED' and a['result']['class']=='AMENDMENT')
    e=rt.mutate(case.object_id,'KEX://DOMAIN/CASEPATH.COM.AU',{'new_class_id':'app://casepath/addressable-runtime','carrier_schema':'keddeh.runtime-carrier.v2','new_addresses':['KEX://DOMAIN/CASEPATH.COM.AU/RING1']})
    t('topology_change_evolves',e['result']['class']=='EVOLUTION')
    t('public_readback_is_continue',rt.ingest_observer('observer://public-http',case.object_id,'PUBLIC_READBACK',{'status':200})['decision']['action']=='CONTINUE')
    rt.ingest_observer('observer://proof',case.object_id,'CONTRADICTION',{'detail':'scope mismatch'})
    t('contradiction_enqueues_repair',any(c.state=='READY' and c.process_id=='process://runtime/reconcile' for c in rt.continuations.queue.values()))
    t('repair_continuation_runs',rt.continuation_tick()['status']=='COMPLETED')
    t('checkpoint',rt.checkpoint()['status']=='CHECKPOINTED')
for n,c in T: print(('PASS' if c else 'FAIL')+':'+n)
raise SystemExit(0 if all(c for _,c in T) else 2)
