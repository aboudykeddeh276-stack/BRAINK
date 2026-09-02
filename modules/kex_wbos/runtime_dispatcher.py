from pathlib import Path
import json,os,sys,urllib.request
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from enterprise.runtime.process_supervisor import ManagedProcess
from runtime.runtime_registry import RuntimeRegistry
from runtime.runtime_route_registry import RuntimeRouteRegistry
class RuntimeDispatcher:
 def __init__(self,root,registry_path=None):
  self.root=Path(root).resolve();self.registry=RuntimeRegistry(registry_path or self.root/'runtime/runtime_registry.sqlite3');self.routes=RuntimeRouteRegistry(root);self.processes={}
 def register_route(self,route,desired_state='STOPPED'):
  s=self.routes.resolve(route);s['command_route']=route;s['desired_state']=desired_state;s['observed_state']='DEFINED'
  s['argv']=[(str(self.root/x) if i and isinstance(x,str) and x.endswith('.py') and not os.path.isabs(x) else x) for i,x in enumerate(s['argv'])]
  return self.registry.upsert(s)
 def _probe(self,url):
  if not url:return {'ok':True}
  try:
   with urllib.request.urlopen(url,timeout=1) as r:return {'ok':r.status<400,'status':r.status}
  except Exception as e:return {'ok':False,'error':type(e).__name__,'detail':str(e)}
 def start(self,rid):
  r=self.registry.get(rid);mp=ManagedProcess(rid,json.loads(r['argv_json']));pid=mp.start();self.processes[rid]=mp
  ready=mp.wait_ready(lambda:self._probe(r['health_endpoint'])['ok'],5) if r['health_endpoint'] else mp.alive();rb=self._probe(r['health_endpoint'])
  return self.registry.observe(rid,pid=pid,generation=mp.generation,observed_state='READY' if ready else 'DEGRADED',restart_count=mp.restart_count,last_readback=rb,last_failure=mp.last_failure)
 def stop(self,rid):
  mp=self.processes.get(rid)
  if mp:mp.stop()
  return self.registry.observe(rid,pid=None,observed_state='STOPPED',last_readback={'ok':True,'stopped':True})
 def restart(self,rid):
  mp=self.processes.get(rid)
  if not mp:return self.start(rid)
  pid=mp.restart();r=self.registry.get(rid);ready=mp.wait_ready(lambda:self._probe(r['health_endpoint'])['ok'],5)
  return self.registry.observe(rid,pid=pid,generation=mp.generation,observed_state='READY' if ready else 'DEGRADED',restart_count=mp.restart_count,last_readback=self._probe(r['health_endpoint']),last_failure=mp.last_failure)
 def readback(self,rid):
  r=self.registry.get(rid);mp=self.processes.get(rid);rb=self._probe(r['health_endpoint']) if r['health_endpoint'] else {'ok':bool(mp and mp.alive())};state='READY' if rb['ok'] else ('STOPPED' if not mp or not mp.alive() else 'DEGRADED')
  return self.registry.observe(rid,pid=(mp.proc.pid if mp and mp.alive() else None),generation=(mp.generation if mp else r['generation']),observed_state=state,restart_count=(mp.restart_count if mp else r['restart_count']),last_readback=rb,last_failure=(mp.last_failure if mp else r['last_failure']))
 def operate(self,action,payload):
  if action=='REGISTER':return self.register_route(payload['command_route'],payload.get('desired_state','STOPPED'))
  if action=='START':return self.start(payload['runtime_id'])
  if action=='STOP':return self.stop(payload['runtime_id'])
  if action=='RESTART':return self.restart(payload['runtime_id'])
  if action=='READBACK':return self.readback(payload['runtime_id'])
  raise ValueError('UNKNOWN_RUNTIME_ACTION')
