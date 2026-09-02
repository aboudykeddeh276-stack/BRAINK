#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
REPORT=BASE/'reports/kex-wbos/tl2-deployment.json'
PROOF=BASE/'reports/kex-wbos/tl2-proof-ledger.jsonl'
CANONICAL_HTTP=BASE/'reports/kex-wbos/canonical-http-ledger.jsonl'
SOURCE_ID='source://github/BRAINK/modules/kex_wbos/action_server.py'
SERVICE_ID='service://wbos/action-server'
RUNTIME_ID='runtime://kex/wbos'
TL2_ID='tlvpn://kex/tl2'

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
def _canonical_readback():
    if not CANONICAL_HTTP.exists():
        return {'ok':False,'state':'MISSING','receipts':0,'reason':'canonical HTTP ledger not produced by runtime'}
    rows=[]
    for line in CANONICAL_HTTP.read_text(encoding='utf-8').splitlines():
        try:
            row=json.loads(line)
            if row.get('schema')=='kex.wbos-canonical-http.v1': rows.append(row)
        except Exception: pass
    egress=[r for r in rows if r.get('direction')=='EGRESS']
    preserved=bool(egress) and all(r.get('identityPreserved') is True for r in egress)
    classified=bool(egress) and all(r.get('measurementClass')=='STRUCTURAL_PROXY' for r in egress)
    return {
        'ok':len(egress)>=4 and preserved and classified,
        'state':'VERIFIED' if len(egress)>=4 and preserved and classified else 'FAIL',
        'receipts':len(rows),
        'egressReceipts':len(egress),
        'identityPreserved':preserved,
        'measurementClass':'STRUCTURAL_PROXY' if classified else 'INVALID_OR_MISSING',
        'ledger':str(CANONICAL_HTTP.relative_to(BASE)),
    }
def _spawn(host,port):
    code=f"import sys; sys.path.insert(0,{str(BASE/'modules/kex_wbos')!r}); import action_server; action_server.serve({host!r},{port})"
    env=os.environ.copy(); env['RUNNER_TRACKING_ID']=''
    return subprocess.Popen([sys.executable,'-c',code],cwd=BASE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,env=env)
def deploy(daemon):
    host,src=_detect(); REPORT.parent.mkdir(parents=True,exist_ok=True)
    if not host:
        r={'status':'BLOCKED_TL2_ACTUATOR','promotion':None,'identity':TL2_ID,'source_object':SOURCE_ID,'service':SERVICE_ID,'runtime':RUNTIME_ID,'reason':'No KEX_TL2_ADDRESS or observed TL2/tunnel interface address','unrelated_blocks_excluded':['PUBLIC_DNS','PUBLIC_TLS','DRIVE_WRITEBACK','BITCOIN_IBD','BRAINK_FULL_MIGRATION']}; REPORT.write_text(json.dumps(r,indent=2)+'\n'); _proof('TL2_BIND_BLOCKED',r); print(json.dumps(r,indent=2)); return 2
    s=socket.socket()
    try: s.bind((host,0))
    except OSError as e:
        r={'status':'BLOCKED_TL2_BIND','promotion':None,'identity':TL2_ID,'address':host,'error':str(e)}; REPORT.write_text(json.dumps(r,indent=2)+'\n'); _proof('TL2_BIND_BLOCKED',r); print(json.dumps(r,indent=2)); return 3
    finally: s.close()
    if CANONICAL_HTTP.exists(): CANONICAL_HTTP.unlink()
    _proof('TL2_SOURCE_BOUND',{'source_object':SOURCE_ID,'service':SERVICE_ID,'runtime':RUNTIME_ID,'transport':TL2_ID})
    _proof('TL2_TUNNEL_BOUND',{'identity':TL2_ID,'address':host,'source':src})
    p=_spawn(host,8790)
    checks=[_wait(f'http://{host}:8790/api/health'),_wait(f'http://{host}:8790/api/services'),_wait(f'http://{host}:8790/api/routes'),_wait(f'http://{host}:8790/api/proof-ledger')]
    canonical=_canonical_readback()
    ok=all(c['ok'] for c in checks) and canonical['ok']
    r={'status':'VERIFIED' if ok else 'FAIL','promotion':'TL2_LIVE' if ok else None,'identity':TL2_ID,'address':host,'identity_source':src,'source_object':SOURCE_ID,'service':SERVICE_ID,'runtime':RUNTIME_ID,'process':{'pid':p.pid,'port':8790},'readback':checks,'canonicalState':canonical,'proof_ledger':str(PROOF.relative_to(BASE)),'excluded_from_deploy':['PUBLIC_LIVE','LIBRARY_PERSISTED','BITCOIN_LIVE','BRAINK_MIGRATED'],'claimBoundary':'TL2_LIVE requires observed HTTP readback plus canonical JSON egress receipts. It does not claim public deployment or physical propagation performance.'}
    REPORT.write_text(json.dumps(r,indent=2)+'\n'); _proof('TL2_DEPLOYMENT_READBACK',r); print(json.dumps(r,indent=2))
    if not ok or not daemon: p.terminate()
    return 0 if ok else 4
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--daemon',action='store_true'); raise SystemExit(deploy(p.parse_args().daemon))
