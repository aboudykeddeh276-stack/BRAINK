from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse, json, sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from enterprise.recursive_computer_runtime_r26 import RecursiveComputer
from runtime.R25.system_evolution_runtime import sha256_json

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
class RuntimeHost:
 def __init__(self,state_root,computer_id='A'):
  self.state_root=Path(state_root); self.state_root.mkdir(parents=True,exist_ok=True)
  self.computer=RecursiveComputer.restore_tree(self.state_root) if (self.state_root/'computer.json').exists() else RecursiveComputer(computer_id=computer_id,state_root=self.state_root)
 def restore(self): self.computer=RecursiveComputer.restore_tree(self.state_root); return self.snapshot(self.computer,'RESTORED')
 def resolve(self,lineage=None):
  lineage=lineage or [self.computer.identity.computer_id]
  if isinstance(lineage,str): lineage=[x for x in lineage.strip('/').split('/') if x]
  if not lineage or lineage[0]!=self.computer.identity.computer_id: raise ValueError('LINEAGE_ROOT_MISMATCH')
  node=self.computer
  for cid in lineage[1:]:
   if cid not in node.children:
    child_root=node.state_root/'descendants'/cid
    if not (child_root/'computer.json').exists(): raise ValueError('COMPUTER_NOT_FOUND:'+cid)
    node.children[cid]=RecursiveComputer.restore_tree(child_root)
   node=node.children[cid]
  return node
 def snapshot(self,node=None,status='RUNNING'):
  node=node or self.computer; rb=node.readback(); return {'status':status,'computer_id':node.identity.computer_id,'generation':node.identity.generation,'lineage':list(node.identity.lineage),'constructor_id':node.identity.constructor_id,'state_root':sha256_json(rb),'state':rb['state'],'memory':rb['memory'],'children':rb['children'],'ledger_verified':node.ledger.verify(),'ledger_events':len(node.ledger.events)}
 def instantiate(self,parent_lineage,child_id):
  parent=self.resolve(parent_lineage); child=parent.instantiate(child_id); return self.snapshot(child,'SUCCESSOR_CREATED')
 def write_memory(self,lineage,k,v): node=self.resolve(lineage); node.write_memory(k,v); return self.snapshot(node)
 def write_state(self,lineage,k,v): node=self.resolve(lineage); node.write_state(k,v); return self.snapshot(node)
 def reconcile(self,lineage):
  node=self.resolve(lineage); result=node.reconcile_once(); return {'status':'RECONCILED' if result.get('status')=='COMPLETED' else result.get('status'),'lineage':list(node.identity.lineage),'continuation':result,'snapshot':self.snapshot(node)}
class Handler(BaseHTTPRequestHandler):
 host_runtime=None
 def reply(self,code,obj):
  b=canonical(obj); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
 def body(self): n=int(self.headers.get('Content-Length','0') or '0'); return json.loads(self.rfile.read(n) or b'{}')
 def do_GET(self):
  u=urlparse(self.path); q=parse_qs(u.query)
  try:
   if u.path=='/health':
    s=self.host_runtime.snapshot(); return self.reply(200,{'status':'PASS','runtime':'BRAINK_RECURSIVE_COMPUTER_R26','constructor_id':s['constructor_id'],'computer_id':s['computer_id'],'state_root':s['state_root'],'ledger_verified':s['ledger_verified']})
   if u.path=='/state': return self.reply(200,self.host_runtime.snapshot(self.host_runtime.resolve(q.get('lineage',[None])[0])))
   return self.reply(404,{'status':'NOT_FOUND'})
  except (KeyError,ValueError) as e: return self.reply(404,{'status':'REJECTED','reason':str(e)})
  except Exception as e: return self.reply(500,{'status':'ERROR','error':type(e).__name__+':'+str(e)})
 def do_POST(self):
  p=urlparse(self.path).path
  try:
   b=self.body(); lineage=b.get('lineage')
   if p=='/instantiate': return self.reply(200,self.host_runtime.instantiate(lineage,b['child_id']))
   if p=='/memory': return self.reply(200,self.host_runtime.write_memory(lineage,b['key'],b.get('value')))
   if p=='/state': return self.reply(200,self.host_runtime.write_state(lineage,b['key'],b.get('value')))
   if p=='/restore': return self.reply(200,self.host_runtime.restore())
   if p=='/reconcile': return self.reply(200,self.host_runtime.reconcile(lineage))
   return self.reply(404,{'status':'NOT_FOUND'})
  except (KeyError,ValueError) as e: return self.reply(400,{'status':'REJECTED','reason':str(e)})
  except Exception as e: return self.reply(409 if 'STALE_STATE_CONFLICT' in str(e) else 500,{'status':'ERROR','error':type(e).__name__+':'+str(e)})
 def log_message(self,*_): pass

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--state-root',required=True); ap.add_argument('--computer-id',default='A'); ap.add_argument('--host',default='127.0.0.1'); ap.add_argument('--port',type=int,default=8811); a=ap.parse_args(); Handler.host_runtime=RuntimeHost(a.state_root,a.computer_id); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=='__main__': main()
