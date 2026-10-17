from __future__ import annotations
import argparse,hmac,json,os,signal,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from enterprise.recursive_computer_runtime_r26 import RecursiveComputer
from enterprise.illlm_authority import ILLLMAuthority
from enterprise.system_contract_registry import SystemContractRegistry

class RuntimeHost:
    def __init__(self,state_root,computer_id='A'):
        self.state_root=Path(state_root); self.computer_id=computer_id; self._lock=threading.RLock(); self.started_ns=time.time_ns()
        if (self.state_root/'computer.json').exists(): self.root=RecursiveComputer.restore_tree(self.state_root)
        else: self.root=RecursiveComputer(computer_id=computer_id,state_root=self.state_root)
        self.illlm=ILLLMAuthority(self.state_root/'control'/'illlm-execution-ledger.json')
        graph_path=Path(__file__).resolve().parents[1]/'control'/'SYSTEM_INTERFACE_GRAPH_R35.json'
        self.system_contracts=SystemContractRegistry(graph_path)
    def resolve(self,lineage):
        parts=lineage.split('/') if isinstance(lineage,str) else list(lineage)
        if not parts or parts[0]!=self.root.identity.computer_id: raise KeyError('UNKNOWN_ROOT')
        node=self.root
        for child_id in parts[1:]:
            if child_id not in node.children: node=RecursiveComputer.restore_tree(node.state_root/'descendants'/child_id)
            else: node=node.children[child_id]
        return node
    def snapshot(self,node=None):
        node=node or self.root; committed=node.readback()
        return {'computer_id':node.identity.computer_id,'lineage':list(node.identity.lineage),'generation':node.identity.generation,'state':committed['state'],'memory':committed['memory'],'children':committed['children'],'constructor':committed['constructor'],'ledger_verified':node.ledger.verify()}
    def health(self): return {'status':'LIVE','pid':os.getpid(),'uptime_ns':time.time_ns()-self.started_ns}
    def ready(self):
        try:
            snap=self.root.readback(); ledger_ok=self.root.ledger.verify()
            contracts=self.system_contracts.verify(); ready=ledger_ok and contracts['status']=='VERIFIED'
            return {'status':'READY' if ready else 'NOT_READY','state_readable':bool(snap),'ledger_verified':ledger_ok,'system_graph_verified':contracts['status']=='VERIFIED','component_count':contracts['component_count'],'constructor':snap.get('constructor')}
        except Exception as exc:return {'status':'NOT_READY','error':type(exc).__name__+':'+str(exc)}
    def write_state(self,lineage,key,value):
        with self._lock:
            node=self.resolve(lineage); node.write_state(key,value); return self.snapshot(node)
    def write_memory(self,lineage,key,value):
        with self._lock:
            node=self.resolve(lineage); node.write_memory(key,value); return self.snapshot(node)
    def instantiate(self,lineage,child_id):
        with self._lock:
            node=self.resolve(lineage); child=node.instantiate(child_id); return self.snapshot(child)
    def illlm_execute(self,request):
        with self._lock: return self.illlm.execute(request,self)

class Handler(BaseHTTPRequestHandler):
    host_runtime:RuntimeHost=None; auth_token:str|None=None
    server_version='KEDDEH-KEX-RUNTIME/R35'
    def log_message(self,fmt,*args): return
    def _json(self,status,payload):
        raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def _body(self):
        n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or b'{}')
    def _authorized(self,path):
        if path in {'/healthz','/readyz'}: return True
        if self.auth_token is None:return False
        supplied=self.headers.get('Authorization','')
        return supplied.startswith('Bearer ') and hmac.compare_digest(supplied[7:],self.auth_token)
    def do_GET(self):
        path=urlparse(self.path).path
        if not self._authorized(path): return self._json(401,{'status':'UNAUTHORIZED'})
        if path=='/healthz': return self._json(200,self.host_runtime.health())
        if path=='/readyz':
            out=self.host_runtime.ready(); return self._json(200 if out['status']=='READY' else 503,out)
        if path=='/v1/root': return self._json(200,self.host_runtime.snapshot())
        if path=='/v1/system-graph': return self._json(200,self.host_runtime.system_contracts.snapshot())
        if path.startswith('/v1/computers/'):
            lineage=path.removeprefix('/v1/computers/')
            try:return self._json(200,self.host_runtime.snapshot(self.host_runtime.resolve(lineage)))
            except Exception as exc:return self._json(404,{'status':'NOT_FOUND','error':str(exc)})
        return self._json(404,{'status':'NOT_FOUND'})
    def do_POST(self):
        path=urlparse(self.path).path
        if not self._authorized(path): return self._json(401,{'status':'UNAUTHORIZED'})
        try: body=self._body()
        except Exception:return self._json(400,{'status':'INVALID_JSON'})
        try:
            if path=='/v1/state': out=self.host_runtime.write_state(body['lineage'],body['key'],body.get('value'))
            elif path=='/v1/memory': out=self.host_runtime.write_memory(body['lineage'],body['key'],body.get('value'))
            elif path=='/v1/instantiate': out=self.host_runtime.instantiate(body['lineage'],body['child_id'])
            elif path=='/v1/illlm/execute': out=self.host_runtime.illlm_execute(body)
            else:return self._json(404,{'status':'NOT_FOUND'})
            return self._json(200,{'status':'COMMITTED','result':out})
        except (KeyError,ValueError) as exc:return self._json(409,{'status':'REJECTED','error':type(exc).__name__+':'+str(exc)})
        except Exception as exc:return self._json(500,{'status':'ERROR','error':type(exc).__name__+':'+str(exc)})

def build_server(state_root,computer_id='A',host='127.0.0.1',port=8811,auth_token=None):
    Handler.host_runtime=RuntimeHost(state_root,computer_id); Handler.auth_token=auth_token
    return ThreadingHTTPServer((host,port),Handler)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--state-root',required=True);p.add_argument('--computer-id',default='A');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8811);p.add_argument('--auth-token-env',default='KEX_AUTH_TOKEN');a=p.parse_args()
    token=os.environ.get(a.auth_token_env)
    if a.host not in {'127.0.0.1','::1','localhost'} and not token: raise SystemExit('NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN')
    server=build_server(a.state_root,a.computer_id,a.host,a.port,token)
    def stop(*_): threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:server.serve_forever()
    finally:server.server_close()
if __name__=='__main__':main()
