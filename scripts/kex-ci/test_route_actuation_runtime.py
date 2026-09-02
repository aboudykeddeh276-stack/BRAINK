import tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.tot_orc_dispatcher import ToTOrcDispatcher
from enterprise.production_actuator_adapter import ProductionActuatorAdapter

T=[]
def t(n,c):T.append((n,bool(c)))
d=ToTOrcDispatcher(); d.register_handler('TL2',lambda c:{'status':'FAILED'}); d.register_handler('TL1',lambda c:{'status':'DISPATCHED'}); d.register_handler('VPN-TL',lambda c:{'status':'DISPATCHED'})
r=d.dispatch({'continuation_id':'continuation://test'}); t('tl_failover',r['carrier']=='TL1')
d.set_availability('TL1',False);d.set_availability('TL2',False);t('vpn_fallback',d.dispatch({'continuation_id':'continuation://test2'})['carrier']=='VPN-TL')
with tempfile.TemporaryDirectory() as td:
 p=Path(td); origin=p/'origin';origin.mkdir(); mock=p/'mock.py'; mock.write_text("import argparse,json\nap=argparse.ArgumentParser();s=ap.add_subparsers(dest='cmd',required=True)\nfor n in ['validate-origin','amend','release','readback']:\n q=s.add_parser(n);q.add_argument('--origin');q.add_argument('--target');q.add_argument('--patch-id');q.add_argument('--release-id');q.add_argument('--target-url')\na=ap.parse_args();print(json.dumps(vars(a)))")
 a=ProductionActuatorAdapter(str(mock));t('probe',a.probe('actuator://casepath')['status']=='READY');t('origin_gate',a.apply('actuator://casepath','app://casepath','AMEND',{'target':'/your-data.html','patch_id':'CP-TC-20260727-C01'})['status']=='ORIGIN_UNBOUND');t('amend',a.apply('actuator://casepath','app://casepath','AMEND',{'origin':str(origin),'target':'/your-data.html','patch_id':'CP-TC-20260727-C01'})['status']=='EXECUTED')
for n,c in T:print(('PASS' if c else 'FAIL')+':'+n)
raise SystemExit(0 if all(c for _,c in T) else 2)
