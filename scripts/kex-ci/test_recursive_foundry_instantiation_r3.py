import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.foundry.market_operating_foundries import MarketOperatingFoundry

with tempfile.TemporaryDirectory() as td:
    base=Path(td)
    master=ROOT/'enterprise/foundry/MASTER_DATASET_R1.json'
    A=MarketOperatingFoundry(master,base/'A',identity='computer://A',continuation='INSTANTIATE_B')
    a=A.build('frontage_website_fleet')
    b=A.instantiate_child('frontage_website_fleet','domain_dns','B',continuation='INSTANTIATE_C')
    B=MarketOperatingFoundry(master,Path(b['child_root']),identity=b['child_identity'],parent_identity='computer://A',continuation='INSTANTIATE_C')
    c=B.instantiate_child('domain_dns','observability','C',continuation='CONTINUE')
    bm=b['manifest']; cm=c['manifest']
    checks={
      'A_identity':a['runtime_identity']=='computer://A',
      'B_parent':bm['parent_identity']=='computer://A',
      'C_parent':cm['parent_identity']==b['child_identity'],
      'same_master_root':len({a['master_root'],bm['master_root'],cm['master_root']})==1,
      'B_continuation':bm['continuation']=='INSTANTIATE_C',
      'C_continuation':cm['continuation']=='CONTINUE',
      'manifest_roots':all(len(x['manifest_root'])==64 for x in (a,bm,cm)),
      'C_runtime_state_exists':(Path(c['child_root'])/'observability'/'telemetry.sqlite3').exists()
    }
    print(json.dumps({'checks':checks,'A':a,'B':b,'C':c},indent=2))
    raise SystemExit(0 if all(checks.values()) else 2)
