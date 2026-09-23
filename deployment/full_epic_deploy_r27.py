#!/usr/bin/env python3
from __future__ import annotations
import argparse,http.client,json,os,socket,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_STATE=Path(os.getenv('BRAINK_EPIC_STATE_ROOT','.braink/full-epic-r27'))

def port_open(port,host='127.0.0.1'):
    s=socket.socket(); s.settimeout(.25)
    try: s.connect((host,port)); return True
    except OSError: return False
    finally: s.close()

def spawn(cmd,log,env=None):
    log.parent.mkdir(parents=True,exist_ok=True); fh=open(log,'ab',buffering=0)
    return subprocess.Popen(cmd,cwd=ROOT,stdout=fh,stderr=fh,start_new_session=True,env={**os.environ,**(env or {})}).pid

def get_json(port,path,headers=None):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=4); c.request('GET',path,headers=headers or {}); r=c.getresponse(); body=r.read(); c.close(); return r.status,json.loads(body)

def frontend(domain):
    c=http.client.HTTPConnection('127.0.0.1',8899,timeout=4); c.request('GET','/',headers={'Host':domain}); r=c.getresponse(); body=r.read(); out={'status':r.status,'bytes':len(body),'contract':r.getheader('x-kex-contract'),'coordinate':r.getheader('x-kex-coordinate')}; c.close(); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--state-root',default=str(DEFAULT_STATE)); ap.add_argument('--verify-only',action='store_true'); ns=ap.parse_args(); state=Path(ns.state_root).resolve(); state.mkdir(parents=True,exist_ok=True); pids={}
    specs=[
      ('gateway',8799,[sys.executable,str(ROOT/'runtime/public_gateway.py')],{'BRAINK_BIND':'127.0.0.1','BRAINK_PORT':'8799'}),
      ('oauth',None,[sys.executable,str(ROOT/'runtime/google_oauth_rail.py')],{}),
      ('stripe',None,[sys.executable,str(ROOT/'runtime/stripe_payment_rail.py')],{}),
      ('site_user',8901,[sys.executable,'-m','http.server','8901','--bind','127.0.0.1','--directory',str(ROOT/'sites/braink.com.au')],{}),
      ('site_intelligence',8902,[sys.executable,'-m','http.server','8902','--bind','127.0.0.1','--directory',str(ROOT/'sites/braink-intelligence.com.au')],{}),
      ('site_learning',8903,[sys.executable,'-m','http.server','8903','--bind','127.0.0.1','--directory',str(ROOT/'sites/braink-learning.com.au')],{}),
    ]
    if not ns.verify_only:
        for name,port,cmd,env in specs:
            if port is None:
                sock={'oauth':'/tmp/braink-oauth.sock','stripe':'/tmp/braink-stripe.sock'}[name]
                if Path(sock).exists(): continue
            elif port_open(port): continue
            pids[name]=spawn(cmd,state/f'{name}.log',env)
        if not port_open(8811): pids['r26']=spawn([sys.executable,str(ROOT/'deployment/recursive_computer_service_r26.py'),'--state-root',str(state/'computer/A'),'--host','127.0.0.1','--port','8811'],state/'r26.log',{'PYTHONPATH':str(ROOT)})
        if not port_open(8899): pids['edge']=spawn(['node',str(ROOT/'deployment/kex_keddeh_edge_node_v49_proxy.cjs')],state/'edge.log',{'KEX_EDGE_HOST':'0.0.0.0','KEX_EDGE_PORT':'8899','KEX_EDGE_STATE_DIR':str(state/'edge-v49')})
        time.sleep(1)
    orchestrator=ROOT/'runtime/agents/BRAINK_PUBLIC_SERVICE_AGENT_ORCHESTRATOR.py'
    graph=json.loads(subprocess.check_output([sys.executable,str(orchestrator)],text=True)); dispatched=[]
    for process_id in graph['processes']:
        p=subprocess.run([sys.executable,str(orchestrator),process_id],input=json.dumps({'intent':'FULL_EPIC_DEPLOYMENT','authority':'KEDDEH_SYSTEMS','phase':'R27'}),text=True,capture_output=True,timeout=5,check=True); dispatched.append(json.loads(p.stdout))
    p17=subprocess.run([sys.executable,str(ROOT/'deployment/p17/KEX_P17_MULTI_EMULATOR_FANOUT_IGNITION.py'),'--nodes',str(ROOT/'deployment/p17/NODES.example.json'),'--target-identity','edge://keddeh/public/tl2','--authority-epoch','7','--dry-run'],text=True,capture_output=True,timeout=10,check=True); p17r=json.loads(p17.stdout)
    checks={}; checks['gateway']=get_json(8799,'/health')[1]; checks['edge']=get_json(8899,'/__kex/edge/status',{'Host':'braink.com.au'})[1]; checks['r26']=get_json(8899,'/runtime/recursive/health',{'Host':'braink.com.au'})[1]; checks['frontages']={d:frontend(d) for d in ('braink.com.au','braink-intelligence.com.au','braink-learning.com.au')}; checks['agent_fabric']={'process_count':len(dispatched),'all_dispatched':all(x.get('state')=='STATE_DISPATCHED' for x in dispatched)}; checks['p17']={'state':p17r['state'],'manifestation_count':p17r['manifestation_count'],'target':p17r['shared_target_identity']}; checks['rails']={'oauth_socket':Path('/tmp/braink-oauth.sock').exists(),'stripe_socket':Path('/tmp/braink-stripe.sock').exists(),'oauth_secret':Path('/run/keddeh/secrets/google-oauth.json').exists(),'stripe_secret':Path('/run/keddeh/secrets/stripe.json').exists()}
    ok=checks['gateway'].get('status')=='PASS' and checks['edge'].get('lifecycle')=='READY' and checks['r26'].get('status')=='PASS' and all(x['status']==200 for x in checks['frontages'].values()) and checks['agent_fabric']['all_dispatched'] and checks['p17']['state']=='DRY_RUN_VALIDATED'
    receipt={'schema':'kex.braink.full-epic-deployment.r27/v1','status':'DEPLOYED_LOCAL_VERIFIED' if ok else 'PARTIAL','pids':pids,'checks':checks,'boundary':{'public_name_authority':checks['edge']['external']['public_name_authority'],'authoritative_dns':checks['edge']['external']['authoritative_dns'],'tls_identity':checks['edge']['external']['tls_identity'],'public_ingress':checks['edge']['external']['public_ingress'],'oauth_secret_hydrated':checks['rails']['oauth_secret'],'stripe_secret_hydrated':checks['rails']['stripe_secret'],'p17_remote_host_hydrated':bool(os.getenv('KEX_P17_REMOTE_HOST')),'p17_secret_hydrated':bool(os.getenv('KEX_P17_SECRET'))}}
    out=state/'FULL_EPIC_DEPLOYMENT_R27_RECEIPT.json'; out.write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt,indent=2)); return 0 if ok else 2
if __name__=='__main__': raise SystemExit(main())
