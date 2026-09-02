import json,sys,tempfile,shutil,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.foundry.market_operating_foundries import MarketOperatingFoundry
MASTER=ROOT/'enterprise/foundry/MASTER_DATASET_R1.json'
lat=[]
for i in range(100):
    td=Path(tempfile.mkdtemp())
    try:
        a=MarketOperatingFoundry(MASTER,td/'A',identity='computer://A')
        a.build('domain_dns')
        mp=td/'A/domain_dns/FOUNDRY_MANIFEST.json'
        t=time.perf_counter_ns(); b=MarketOperatingFoundry.rehydrate(mp); lat.append((time.perf_counter_ns()-t)/1e6)
        assert b.identity=='computer://A'
    finally:
        shutil.rmtree(td)
td=Path(tempfile.mkdtemp()); blocked=False
try:
    a=MarketOperatingFoundry(MASTER,td/'A',identity='computer://A'); a.build('domain_dns')
    mp=td/'A/domain_dns/FOUNDRY_MANIFEST.json'; m=json.loads(mp.read_text()); m['runtime_identity']='computer://ATTACKER'; mp.write_text(json.dumps(m))
    try: MarketOperatingFoundry.rehydrate(mp)
    except ValueError: blocked=True
finally:
    shutil.rmtree(td)
result={'valid_rehydrate_runs':100,'median_verify_rehydrate_ms':statistics.median(lat),'max_ms':max(lat),'tamper_blocked':blocked}
print(json.dumps(result,indent=2))
raise SystemExit(0 if blocked else 2)
