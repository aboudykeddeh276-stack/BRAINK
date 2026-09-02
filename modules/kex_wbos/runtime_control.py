from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from modules.kex_wbos.runtime_dispatcher import RuntimeDispatcher
from runtime.reconciler import RuntimeReconciler
_DISPATCHER=RuntimeDispatcher(ROOT)
_RECONCILER=RuntimeReconciler(_DISPATCHER)
def runtime_control(payload):
 action=str(payload.get('action','')).upper()
 if action=='RECONCILE':return {'status':'PASS','actions':_RECONCILER.reconcile_once()}
 try:return {'status':'PASS','result':_DISPATCHER.operate(action,payload)}
 except Exception as e:return {'status':'FAIL','error':type(e).__name__,'detail':str(e)}
