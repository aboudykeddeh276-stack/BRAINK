#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; REPORT=BASE/'reports/kex-wbos/tl2-deployment.json'; PROOF=BASE/'reports/kex-wbos/tl2-proof-ledger.jsonl'
def _sha(b): return hashlib.sha256(b).hexdigest()
def _detect():
    if os.getenv('KEX_TL2_ADDRESS'): return os.environ['KEX_TL2_ADDRESS'],'KEX_TL2_ADDRESS'
    try:
        for i in json.loads(subprocess.check_output(['ip','-j','addr'],text=True,stderr=subprocess.DEVNULL)):
            n=str(i.get('ifname','')).lower()
            if any(t in n for t in ('tl2','tlvpn','tailscale','wg','tun')):
                for a in i.get('addr_info',[]):
                    if a.get('family')=='inet' and a.get('local') and not str(a['local']).startswith('127.'):
                        return str(a['local']),i.get('ifname','tunnel')
    except Exception: pass
    return None,'unresolved'
def _proof(event,payload):
    PROOF.parent.mkdir(parents=True,exist_ok=True)
    with PROOF.open('a',encoding='utf-8') as f: f.write(json.dumps({'ts':time.time(),'event':event,**payload},sort_keys=True)+'\n')
def _wait(url,timeout=20):
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                b=r.read(); return {'url':url,'status':r.status,'bytes':len(b),'sha256':_sha(b),'ok':r.status<400}
        except Exception as e: last=type(e).__name__; time.sleep(.25)
    return {'url':url,'status':None,'bytes':0,'sha256':None,'ok':False,'error':last}
def _spawn(module,host,port):
    code=f"import sys; sys.path.insert(0,{str(BASE/'modules/kex_wbos')!r}); import {module}; {module}.serve({host!r},{port})"
    env=os.environ.copy(); env['RUNNER_TRACKING_ID']=''
    return subprocess.Popen([sys.executable,'-c',code],cwd=BASE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env=env)
def deploy(daemon):
    host,src=_detect(); REPORT.parent.mkdir(parents=True,exist_ok=True)
    if not host:
        r={'status':'BLOCKED_TL2_ACTUATOR','promotion':None,'identity':'tlvpn://kex/tl2','reason':'No KEX_TL2_ADDRESS or observed TL2/tunnel interface address','public_promotions':['BLOCKED']}; REPORT.write_text(json.dumps(r,indent=2)+'\n'); _proof('TL2_BIND_BLOCKED',r); print(json.dumps(r,indent=2)); return 2
    s=socket.socket()
    try: s.bind((host,0))
    except OSError as e:
        r={'status':'BLOCKED_TL2_BIND','promotion':None,'address':host,'error':str(e)}; REPORT.write_text(json.dumps(r,indent=2)+'\n'); _proof('TL2_BIND_BLOCKED',r); print(json.dumps(r,indent=2)); return 3
    finally: s.close()
    _proof('TL2_TUNNEL_BOUND',{'identity':'tlvpn://kex/tl2','address':host,'source':src})
    w=_spawn('server',host,8765); a=_spawn('action_server',host,8790)
    checks=[_wait(f'http://{host}:8765/api/health'),_wait(f'http://{host}:8790/api/health'),_wait(f'http://{host}:8790/api/services'),_wait(f'http://{host}:8790/api/routes'),_wait(f'http://{host}:8790/api/proof-ledger')]
    ok=all(c['ok'] for c in checks); r={'status':'VERIFIED' if ok else 'FAIL','promotion':'TL2_LIVE' if ok else None,'identity':'tlvpn://kex/tl2','address':host,'identity_source':src,'services':{'wbos':{'pid':w.pid,'port':8765},'action_runtime':{'pid':a.pid,'port':8790}},'readback':checks,'proof_ledger':str(PROOF.relative_to(BASE)),'public_promotions':['NOT_CLAIMED']}; REPORT.write_text(json.dumps(r,indent=2)+'\n'); _proof('TL2_DEPLOYMENT_READBACK',r); print(json.dumps(r,indent=2))
    if not ok or not daemon:
        for p in (a,w): p.terminate()
    return 0 if ok else 4
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--daemon',action='store_true'); raise SystemExit(deploy(p.parse_args().daemon))
