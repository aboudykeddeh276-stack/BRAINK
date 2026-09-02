import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from modules.kex_wbos.runtime_dispatcher import RuntimeDispatcher
from runtime.reconciler import RuntimeReconciler
db=ROOT/'runtime/test_registry_r27.sqlite3'
if db.exists():db.unlink()
d=RuntimeDispatcher(ROOT,db);r=d.register_route('qualification-http','ACTIVE');rec=RuntimeReconciler(d)
a1=rec.reconcile_once();rb=d.readback('runtime://qualification-http');a2=rec.reconcile_once();st=d.stop('runtime://qualification-http')
checks={'registered':r['observed_state']=='DEFINED','started':any(x['action']=='START' and x['state']=='READY' for x in a1),'readback_ready':rb['observed_state']=='READY','stable_reconcile':any(x['action']=='READBACK' and x['state']=='READY' for x in a2),'stopped':st['observed_state']=='STOPPED','generation_incremented':rb['generation']>=1,'authorship_preserved':rb['author_id']=='AKD','state_root_present':bool(rb['state_root'])}
print(json.dumps({'checks':checks,'runtime':rb,'actions_first':a1,'actions_second':a2},indent=2));raise SystemExit(0 if all(checks.values()) else 2)
