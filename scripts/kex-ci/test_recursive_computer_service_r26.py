from __future__ import annotations
import concurrent.futures
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
SERVICE=ROOT/'deployment'/'recursive_computer_service_r26.py'

def free_port():
    s=socket.socket(); s.bind(('127.0.0.1',0)); port=s.getsockname()[1]; s.close(); return port

def call(base,method,path,body=None,timeout=15):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'} if data else {},method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def wait(base,timeout=10):
    end=time.time()+timeout
    while time.time()<end:
        try:
            h=call(base,'GET','/health',timeout=1)
            if h.get('status')=='PASS': return h
        except Exception: time.sleep(.05)
    raise RuntimeError('SERVICE_START_TIMEOUT')

def start(state_root,port):
    return subprocess.Popen([sys.executable,str(SERVICE),'--state-root',str(state_root),'--computer-id','A','--host','127.0.0.1','--port',str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def stop(p):
    p.terminate()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=5)

def main():
    with tempfile.TemporaryDirectory(prefix='r26-service-test-') as td:
        state=Path(td)/'A'; port=free_port(); base=f'http://127.0.0.1:{port}'
        p=start(state,port)
        try:
            wait(base)
            call(base,'POST','/memory',{'lineage':'A','key':'seed','value':297})
            call(base,'POST','/instantiate',{'lineage':'A','child_id':'B'})
            call(base,'POST','/memory',{'lineage':'A/B','key':'child','value':88})
        finally: stop(p)
        p=start(state,port)
        try:
            wait(base)
            b2=call(base,'GET','/state?lineage=A/B')
            c=call(base,'POST','/instantiate',{'lineage':'A/B','child_id':'C'})
            assert b2['memory']=={'child':88,'seed':297}
            assert c['lineage']==['A','B','C'] and c['memory']=={'child':88,'seed':297}
            kids=[f'D{i:02d}' for i in range(8)]
            def create(k): return call(base,'POST','/instantiate',{'lineage':'A/B/C','child_id':k})
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: results=list(ex.map(create,kids))
            c2=call(base,'GET','/state?lineage=A/B/C')
            assert sorted(c2['children'])==kids and c2['ledger_verified']
            assert all(r['constructor_id']=='constructor://kex/recursive-computer/r26' for r in results)
            topology=call(base,'GET','/topology')
            assert topology['node_count']==11 and topology['max_generation']==3
            checkpoint=call(base,'POST','/checkpoint',{'lineage':'A/B/C'})
            assert checkpoint['status']=='CHECKPOINTED'
            print(json.dumps({'status':'VERIFIED','restart_memory':b2['memory'],'lineage':c['lineage'],'concurrent_children':c2['children'],'ledger_verified':c2['ledger_verified'],'node_count':topology['node_count'],'max_generation':topology['max_generation']},sort_keys=True))
        finally: stop(p)

if __name__=='__main__': main()
