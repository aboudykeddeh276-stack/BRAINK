#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shlex, subprocess, sys, time
from pathlib import Path

SCHEMA='kex.p17.multi-emulator-fanout.v1'

def load_nodes(path: Path):
    raw=json.loads(path.read_text())
    nodes=raw['nodes'] if isinstance(raw,dict) else raw
    if not isinstance(nodes,list) or not nodes: raise SystemExit('NODES_REQUIRED')
    seen=set(); out=[]
    for i,n in enumerate(nodes,1):
        if not isinstance(n,dict): raise SystemExit(f'NODE_{i}_INVALID')
        node_id=str(n.get('node_id') or '').strip()
        if not node_id or node_id in seen: raise SystemExit(f'NODE_ID_INVALID_OR_DUPLICATE:{node_id}')
        seen.add(node_id); x=dict(n); x['node_id']=node_id; x['priority']=int(n.get('priority',i*10)); x['upstream']=str(n.get('upstream') or 'http://127.0.0.1:8799'); x['remote_host']=str(n.get('remote_host') or '${KEX_P17_REMOTE_HOST}'); x['remote_port']=int(n.get('remote_port',9443)); out.append(x)
    return out

def build_cmd(node,args):
    ledger=Path(args.state_dir)/node['node_id']/'p17-launchpad.sqlite3'
    cmd=[sys.executable,'-m','kex_p17.launchpad','--remote-host',node['remote_host'],'--remote-port',str(node['remote_port']),'--hostname',args.hostname,'--route-root',args.route_root,'--parent-lineage',args.parent_lineage,'--braink-root',args.braink_root,'--target-identity',args.target_identity,'--node-id',node['node_id'],'--priority',str(node['priority']),'--authority-epoch',str(args.authority_epoch),'--upstream',node['upstream'],'--ledger',str(ledger)]
    if args.cafile: cmd += ['--cafile',args.cafile]
    if args.client_cert: cmd += ['--client-cert',args.client_cert]
    if args.client_key: cmd += ['--client-key',args.client_key]
    if args.insecure_test_tls: cmd += ['--insecure-test-tls']
    if args.once: cmd += ['--once']
    return cmd,ledger

def main():
    ap=argparse.ArgumentParser(description='KEDDEH P17 multi-emulator fan-out ignition'); ap.add_argument('--nodes',required=True); ap.add_argument('--state-dir',default='./state/fanout'); ap.add_argument('--hostname',default='keddeh.com'); ap.add_argument('--route-root',default='route://keddeh/public/root'); ap.add_argument('--parent-lineage',default='KEX://MESH/KEDDEH/DOMAIN-FABRIC/TOT'); ap.add_argument('--braink-root',default='braink://live-layer/resident-v5/r1'); ap.add_argument('--target-identity',required=True); ap.add_argument('--authority-epoch',type=int,required=True); ap.add_argument('--cafile'); ap.add_argument('--client-cert'); ap.add_argument('--client-key'); ap.add_argument('--insecure-test-tls',action='store_true'); ap.add_argument('--once',action='store_true'); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    nodes=load_nodes(Path(args.nodes)); Path(args.state_dir).mkdir(parents=True,exist_ok=True); plan=[]
    for n in nodes:
        cmd,ledger=build_cmd(n,args); plan.append({'node_id':n['node_id'],'priority':n['priority'],'remote_host':n['remote_host'],'remote_port':n['remote_port'],'upstream':n['upstream'],'ledger':str(ledger),'command':cmd})
    receipt={'schema':SCHEMA,'logical_route':args.route_root,'hostname':args.hostname,'manifestation_count':len(plan),'shared_target_identity':args.target_identity,'authority_epoch':args.authority_epoch,'state':'PLANNED','manifestations':plan}
    if args.dry_run: receipt['state']='DRY_RUN_VALIDATED'; print(json.dumps(receipt,indent=2)); return 0
    if not os.getenv('KEX_P17_SECRET'): receipt['state']='BLOCKED_SECRET_NOT_HYDRATED'; print(json.dumps(receipt,indent=2)); return 3
    procs=[]
    for item in plan:
        Path(item['ledger']).parent.mkdir(parents=True,exist_ok=True); procs.append((item,subprocess.Popen(item['command'],env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)))
    receipt['state']='EXECUTING'
    if args.once:
        results=[]
        for item,p in procs:
            out,err=p.communicate(); results.append({'node_id':item['node_id'],'returncode':p.returncode,'stdout':out[-4000:],'stderr':err[-4000:]})
        receipt['results']=results; receipt['state']='COMPLETED' if all(r['returncode']==0 for r in results) else 'PARTIAL_OR_FAILED'; print(json.dumps(receipt,indent=2)); return 0 if receipt['state']=='COMPLETED' else 2
    print(json.dumps(receipt,indent=2),flush=True)
    try:
        while True:
            dead=[(i,p.returncode) for i,p in procs if p.poll() is not None]
            if dead: print(json.dumps({'schema':SCHEMA,'state':'MANIFESTATION_EXIT','dead':[{'node_id':i['node_id'],'returncode':rc} for i,rc in dead]}),flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        for _,p in procs:
            if p.poll() is None: p.terminate()
        for _,p in procs:
            try:p.wait(timeout=5)
            except: p.kill()
    return 0

if __name__=='__main__': raise SystemExit(main())
