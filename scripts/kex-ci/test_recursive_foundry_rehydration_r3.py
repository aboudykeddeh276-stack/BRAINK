import json,sys,tempfile,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory() as td:
    base=Path(td)
    # Process 1 creates A and B, then exits.
    create_script=base/'create_ab.py'
    create_script.write_text("""
import sys,json
from pathlib import Path
ROOT=Path(sys.argv[1]); BASE=Path(sys.argv[2]); sys.path.insert(0,str(ROOT))
from enterprise.foundry.market_operating_foundries import MarketOperatingFoundry
A=MarketOperatingFoundry(ROOT/'enterprise/foundry/MASTER_DATASET_R1.json',BASE/'A',identity='computer://A',continuation='INSTANTIATE_B')
A.build('frontage_website_fleet')
b=A.instantiate_child('frontage_website_fleet','domain_dns','B',continuation='INSTANTIATE_C')
print(Path(b['child_root'])/'domain_dns/FOUNDRY_MANIFEST.json')
""")
    cp=subprocess.run([sys.executable,str(create_script),str(ROOT),str(base)],capture_output=True,text=True,check=True)
    manifest=Path(cp.stdout.strip())
    persisted=json.loads(manifest.read_text())
    # Process 2 starts with no A/B objects and rehydrates B from its persisted manifest.
    resume_script=base/'resume_b.py'
    resume_script.write_text("""
import sys,json
from pathlib import Path
ROOT=Path(sys.argv[1]); MANIFEST=Path(sys.argv[2]); sys.path.insert(0,str(ROOT))
from enterprise.foundry.market_operating_foundries import MarketOperatingFoundry
B=MarketOperatingFoundry.rehydrate(MANIFEST,ROOT/'enterprise/foundry/MASTER_DATASET_R1.json')
c=B.instantiate_child('domain_dns','observability','C_AFTER_RESTART',continuation='CONTINUE')
print(json.dumps({'identity':B.identity,'parent':B.parent_identity,'continuation':B.continuation,'C':c}))
""")
    rp=subprocess.run([sys.executable,str(resume_script),str(ROOT),str(manifest)],capture_output=True,text=True,check=True)
    out=json.loads(rp.stdout)
    checks={
      'constructor_ref_persisted':persisted['constructor_ref'].endswith(':MarketOperatingFoundry'),
      'identity_restored':out['identity']=='computer://A/frontage_website_fleet/descendant/B',
      'parent_restored':out['parent']=='computer://A',
      'continuation_restored':out['continuation']=='INSTANTIATE_C',
      'master_root_preserved':out['C']['manifest']['master_root']==persisted['master_root'],
      'child_parent_is_rehydrated_B':out['C']['manifest']['parent_identity']==out['identity'],
      'child_runtime_state_exists':(Path(out['C']['child_root'])/'observability'/'telemetry.sqlite3').exists()
    }
    print(json.dumps({'checks':checks,'persisted_B':persisted,'rehydrated':out},indent=2))
    raise SystemExit(0 if all(checks.values()) else 2)
