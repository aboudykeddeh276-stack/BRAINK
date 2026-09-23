#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, pathlib, shutil, subprocess, sys, time, urllib.request, ssl

ROOT=pathlib.Path(__file__).resolve().parent
FABRIC=pathlib.Path(os.environ.get('KEDDEH_DOMAIN_FABRIC_ROOT','/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5'))
EVIDENCE=pathlib.Path(os.environ.get('KEDDEH_EVIDENCE_ROOT','/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE'))
DOMAINS=['braink.com.au','braink-intelligence.com.au','braink-learning.com.au']
DIST=ROOT/'dist'
ROLLBACK=ROOT/'.rollback'/'previous-dist'
RECEIPT=ROOT/'BRAINK_LIVE_DEPLOYMENT_RECEIPT.json'
PUBLIC_TLS_RECEIPT=ROOT/'BRAINK_PUBLIC_TLS_RECEIPT.json'
PUBLIC_TLS_REQUIRED=os.environ.get('KEDDEH_PUBLIC_TLS_REQUIRED','0')=='1'


def run(cmd,**kw):
    p=subprocess.run(cmd,text=True,capture_output=True,**kw)
    if p.returncode:
        raise RuntimeError('COMMAND_FAILED '+repr(cmd)+'\n'+p.stdout+'\n'+p.stderr)
    return p.stdout


def tree_root(path:pathlib.Path)->str|None:
    if not path.exists(): return None
    rows=[]
    for f in sorted(p for p in path.rglob('*') if p.is_file()):
        rows.append((str(f.relative_to(path)),hashlib.sha256(f.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()


def snapshot_previous()->dict:
    ROLLBACK.parent.mkdir(parents=True,exist_ok=True)
    if ROLLBACK.exists(): shutil.rmtree(ROLLBACK)
    existed=DIST.exists(); before=tree_root(DIST)
    if existed: shutil.copytree(DIST,ROLLBACK)
    return {'previous_dist_existed':existed,'previous_dist_root':before}


def restore_previous(snapshot:dict,env:dict)->dict:
    if DIST.exists(): shutil.rmtree(DIST)
    if snapshot['previous_dist_existed'] and ROLLBACK.exists(): shutil.copytree(ROLLBACK,DIST)
    restored=tree_root(DIST); fabric_restart=None
    if snapshot['previous_dist_existed']:
        fabric_restart=run(['bash',str(FABRIC/'START_FULL_DOMAIN_FABRIC.command')],env=env)[-12000:]
    return {'status':'ROLLBACK_EXECUTED','restored_dist_root':restored,'expected_dist_root':snapshot['previous_dist_root'],'root_match':restored==snapshot['previous_dist_root'],'fabric_restart_output':fabric_restart}


def local_readback()->tuple[dict,bool]:
    domains={}; overall=True
    for d in DOMAINS:
        req=urllib.request.Request('https://127.0.0.1:8443/health',headers={'Host':d})
        try:
            body=urllib.request.urlopen(req,context=ssl._create_unverified_context(),timeout=5).read(); data=json.loads(body)
            ok=data.get('state')=='PASS' and data.get('domain')==d
        except Exception as e:
            data={'error':str(e)}; ok=False
        domains[d]={'local_https':ok,'readback':data}; overall &= ok
    return domains,overall


def provision_public_tls(env:dict)->dict:
    env=env.copy()
    env['KEDDEH_PUBLIC_TLS_DOMAINS']=','.join(DOMAINS)
    env['KEDDEH_PUBLIC_TLS_RECEIPT']=str(PUBLIC_TLS_RECEIPT)
    out=run([sys.executable,str(ROOT/'provision_public_tls.py')],env=env)
    if not PUBLIC_TLS_RECEIPT.is_file():
        raise RuntimeError('PUBLIC_TLS_RECEIPT_MISSING\n'+out[-8000:])
    receipt=json.loads(PUBLIC_TLS_RECEIPT.read_text('utf-8'))
    if not receipt.get('overall') or receipt.get('status')!='PUBLIC_TLS_DEPLOYMENT_VERIFIED':
        raise RuntimeError('PUBLIC_TLS_NOT_VERIFIED:'+json.dumps(receipt,sort_keys=True)[-12000:])
    expected=set(DOMAINS); observed=set(receipt.get('domains',{}))
    if expected!=observed:
        raise RuntimeError(f'PUBLIC_TLS_DOMAIN_SET_MISMATCH expected={sorted(expected)} observed={sorted(observed)}')
    for domain in DOMAINS:
        if receipt['domains'][domain].get('state')!='EXTERNALLY_VERIFIED':
            raise RuntimeError(f'PUBLIC_TLS_DOMAIN_NOT_VERIFIED:{domain}')
    return receipt


def main():
    if not (FABRIC/'START_FULL_DOMAIN_FABRIC.command').exists(): raise SystemExit('RESIDENT_DOMAIN_FABRIC_NOT_MOUNTED')
    env=os.environ.copy(); env['KEDDEH_EVIDENCE_ROOT']=str(EVIDENCE)
    snap=snapshot_previous()
    receipt={'schema':'kex.braink.live-deployment.r24/v3','domains':{},'at':time.time(),'overall':False,'r24':{'rollback_ready':True,'snapshot':snap},'public_tls_required':PUBLIC_TLS_REQUIRED,'claim_boundary':'LOCAL_OWNER_HOST_FABRIC_READBACK_NOT_PUBLIC_DNS_TLS_PROOF'}
    try:
        run([sys.executable,str(ROOT/'build_sites.py')])
        receipt['candidate_dist_root']=tree_root(DIST)
        out=run(['bash',str(FABRIC/'START_FULL_DOMAIN_FABRIC.command')],env=env)
        receipt['fabric_output']=out[-12000:]
        receipt['domains'],receipt['overall']=local_readback()
        if not receipt['overall']: raise RuntimeError('LOCAL_HTTPS_READBACK_FAILED')
        receipt['status']='DEPLOYED_LOCAL_OWNER_HOST_READBACK_PASS'
        if PUBLIC_TLS_REQUIRED:
            receipt['public_tls']=provision_public_tls(env)
            receipt['status']='DEPLOYED_PUBLIC_TLS_READBACK_PASS'
            receipt['claim_boundary']='PUBLIC_TLS_SYSTEM_TRUST_AND_HOSTNAME_READBACK_VERIFIED'
        receipt['r24']['rollback_executed']=False
        RECEIPT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        print(json.dumps(receipt,indent=2,sort_keys=True)); return 0
    except Exception as exc:
        receipt['overall']=False
        receipt['status']='DEPLOYMENT_REJECTED_ROLLBACK_REQUIRED'
        receipt['failure']=str(exc)
        if PUBLIC_TLS_RECEIPT.exists():
            try: receipt['public_tls']=json.loads(PUBLIC_TLS_RECEIPT.read_text('utf-8'))
            except Exception: receipt['public_tls']={'status':'RECEIPT_UNREADABLE'}
        try:
            receipt['r24']['rollback']=restore_previous(snap,env)
            receipt['r24']['rollback_executed']=True
        except Exception as rollback_exc:
            receipt['r24']['rollback']={'status':'ROLLBACK_FAILED','error':str(rollback_exc)}
            receipt['r24']['rollback_executed']=True
        RECEIPT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        print(json.dumps(receipt,indent=2,sort_keys=True)); return 2

if __name__=='__main__': raise SystemExit(main())
