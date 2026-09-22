#!/usr/bin/env python3
from pathlib import Path
import os, subprocess, sys, json, re
ROOT=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(ROOT/'materialize_corpus.py')],check=True)
env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'src')
suites=[('baseline_36','tests.test_baseline_progression',36),('distributed_16','tests.test_report03_v3',16),('semantic_boundary_12','tests.test_semantic_boundary_integration',12)]
out=[]
for name,module,expected in suites:
    p=subprocess.run([sys.executable,'-m','unittest','-v',module],cwd=ROOT,env=env,text=True,capture_output=True,timeout=120)
    text=p.stdout+p.stderr
    m=re.search(r'Ran (\d+) tests?',text)
    count=int(m.group(1)) if m else -1
    ok=(p.returncode==0 and count==expected and '\nOK' in text)
    out.append({'name':name,'expected':expected,'observed':count,'pass':ok})
    (ROOT/'evidence'/f'repo_{name}.txt').write_text(text)
    if not ok:
        print(text); raise SystemExit(1)
receipt={'schema':'keddeh.report03.r5.repo-qualification.v1','all_passed':all(x['pass'] for x in out),'total':sum(x['observed'] for x in out),'suites':out}
(ROOT/'evidence'/'REPO_QUALIFICATION_R5.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps(receipt,indent=2))