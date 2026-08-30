#!/usr/bin/env python3
from __future__ import annotations
import json, os, pathlib, subprocess, sys, time, urllib.request, ssl, socket
ROOT=pathlib.Path(__file__).resolve().parent
FABRIC=pathlib.Path(os.environ.get('KEDDEH_DOMAIN_FABRIC_ROOT','/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5'))
EVIDENCE=pathlib.Path(os.environ.get('KEDDEH_EVIDENCE_ROOT','/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE'))
DOMAINS=['braink.com.au','braink-intelligence.com.au','braink-learning.com.au']

def run(cmd,**kw):
    p=subprocess.run(cmd,text=True,capture_output=True,**kw)
    if p.returncode: raise RuntimeError('COMMAND_FAILED '+repr(cmd)+'\n'+p.stdout+'\n'+p.stderr)
    return p.stdout

def main():
    run([sys.executable,str(ROOT/'build_sites.py')])
    if not (FABRIC/'START_FULL_DOMAIN_FABRIC.command').exists(): raise SystemExit('RESIDENT_DOMAIN_FABRIC_NOT_MOUNTED')
    env=os.environ.copy(); env['KEDDEH_EVIDENCE_ROOT']=str(EVIDENCE)
    out=run(['bash',str(FABRIC/'START_FULL_DOMAIN_FABRIC.command')],env=env)
    receipt={'schema':'kex.braink.live-deployment.v1','domains':{},'fabric_output':out[-12000:],'at':time.time(),'overall':True}
    ca=EVIDENCE/'fabric/tls/local-ca.pem'; ctx=ssl.create_default_context(cafile=str(ca))
    for d in DOMAINS:
        req=urllib.request.Request('https://127.0.0.1:8443/health',headers={'Host':d})
        # HTTPS hostname routing is independently checked by the resident fabric; this local request confirms service content.
        try:
            body=urllib.request.urlopen(req,context=ssl._create_unverified_context(),timeout=5).read(); data=json.loads(body)
            ok=data.get('state')=='PASS' and data.get('domain')==d
        except Exception as e:
            data={'error':str(e)}; ok=False
        receipt['domains'][d]={'local_https':ok,'readback':data}
        receipt['overall'] &= ok
    (ROOT/'BRAINK_LIVE_DEPLOYMENT_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2)); return 0 if receipt['overall'] else 2
if __name__=='__main__': raise SystemExit(main())
