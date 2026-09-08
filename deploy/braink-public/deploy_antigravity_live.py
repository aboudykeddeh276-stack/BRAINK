#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, pathlib, shutil, ssl, subprocess, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
FABRIC = pathlib.Path(os.environ.get('KEDDEH_DOMAIN_FABRIC_ROOT','/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5'))
EVIDENCE = pathlib.Path(os.environ.get('KEDDEH_EVIDENCE_ROOT','/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE'))
ORCH = pathlib.Path(os.environ.get('BRAINK_ORCHESTRATOR_SOCKET','/tmp/braink-orchestrator.sock'))
DIST = ROOT / 'dist'
ROLLBACK = ROOT / '.rollback' / 'antigravity-previous-dist'
RECEIPT = ROOT / 'BRAINK_ANTIGRAVITY_DEPLOYMENT_RECEIPT.json'
DOMAINS = ['braink.com.au','braink-intelligence.com.au','braink-learning.com.au']


def run(cmd, **kw):
    p = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if p.returncode:
        raise RuntimeError('COMMAND_FAILED '+repr(cmd)+'\n'+p.stdout+'\n'+p.stderr)
    return p.stdout


def tree_root(path):
    rows=[]
    if path.exists():
        for f in sorted(p for p in path.rglob('*') if p.is_file()):
            rows.append((str(f.relative_to(path)), hashlib.sha256(f.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()


def request(url, host=None, payload=None):
    headers={'content-type':'application/json'}
    if host: headers['Host']=host
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url, headers=headers, data=data, method='GET' if data is None else 'POST')
    with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=15) as r:
        return r.status, json.loads(r.read())


def restore(snapshot, env):
    if DIST.exists(): shutil.rmtree(DIST)
    if snapshot['existed'] and ROLLBACK.exists(): shutil.copytree(ROLLBACK,DIST)
    run(['bash',str(FABRIC/'START_FULL_DOMAIN_FABRIC.command')],env=env)
    return {'status':'ROLLBACK_EXECUTED','root_match':tree_root(DIST)==snapshot['root']}


def main():
    receipt={'schema':'kex.braink.antigravity-deployment.v1','at':time.time(),'overall':False,
             'claim_boundary':'PASS_REQUIRES_RESIDENT_ORCHESTRATOR_DIRECT_GATEWAY_AND_LAYER2_INGRESS_PROOF'}
    env=os.environ.copy(); env['KEDDEH_EVIDENCE_ROOT']=str(EVIDENCE)
    snapshot={'existed':DIST.exists(),'root':tree_root(DIST)}
    ROLLBACK.parent.mkdir(parents=True,exist_ok=True)
    if ROLLBACK.exists(): shutil.rmtree(ROLLBACK)
    if DIST.exists(): shutil.copytree(DIST,ROLLBACK)
    gateway=None
    try:
        if not (FABRIC/'START_FULL_DOMAIN_FABRIC.command').is_file(): raise RuntimeError('RESIDENT_DOMAIN_FABRIC_NOT_MOUNTED')
        if not ORCH.exists() or not ORCH.is_socket(): raise RuntimeError('BRAINK_ORCHESTRATOR_SOCKET_NOT_READY:'+str(ORCH))
        run([sys.executable,str(ROOT/'build_antigravity_sites.py')])
        receipt['candidate_dist_root']=tree_root(DIST)
        receipt['fabric_output']=run(['bash',str(FABRIC/'START_FULL_DOMAIN_FABRIC.command')],env=env)[-12000:]
        gateway=subprocess.Popen([sys.executable,str(ROOT/'antigravity_gateway.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        time.sleep(1)
        code, health=request('http://127.0.0.1:8800/health')
        receipt['direct_gateway_health']={'http':code,'body':health}
        if code != 200 or health.get('status')!='PASS': raise RuntimeError('DIRECT_GATEWAY_HEALTH_FAILED')
        probe={'protocol':'braink.adapter.v1','kind':'intent','correlation_id':'deployment-readback-'+str(int(time.time())),
               'intent':'Return a non-mutating BRAINK Antigravity deployment readiness proof.',
               'actor':{'type':'deployment_verifier'},'context':{'requirements':['ai']},'proof_required':True}
        direct_code,direct=request('http://127.0.0.1:8800/braink/dispatch',payload=probe)
        receipt['direct_dispatch']={'http':direct_code,'body':direct}
        if direct_code != 200 or not direct.get('proof'): raise RuntimeError('DIRECT_ORCHESTRATOR_PROOF_FAILED')
        domains={}
        for domain in DOMAINS:
            try:
                c,b=request('https://127.0.0.1:8443/braink/dispatch',host=domain,payload=probe)
                ok=c==200 and b.get('correlation_id') in (None,probe['correlation_id']) and bool(b.get('proof'))
                domains[domain]={'http':c,'proof':bool(b.get('proof')),'status':'PASS' if ok else 'FAIL','body':b}
            except Exception as exc:
                domains[domain]={'status':'FAIL','error':str(exc)}; ok=False
            if not ok: raise RuntimeError('LAYER2_INGRESS_DISPATCH_FAILED:'+domain)
        receipt['domains']=domains
        receipt['overall']=True; receipt['status']='DEPLOYED_ANTIGRAVITY_LAYER2_READBACK_PASS'
        RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt,indent=2)); return 0
    except Exception as exc:
        receipt['status']='DEPLOYMENT_REJECTED'; receipt['failure']=str(exc)
        try: receipt['rollback']=restore(snapshot,env)
        except Exception as rb: receipt['rollback']={'status':'ROLLBACK_FAILED','error':str(rb)}
        RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt,indent=2)); return 2
    finally:
        if gateway and gateway.poll() is None:
            gateway.terminate()
            try: gateway.wait(timeout=3)
            except Exception: gateway.kill()

if __name__=='__main__': raise SystemExit(main())
