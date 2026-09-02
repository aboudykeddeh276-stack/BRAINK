class RuntimeReconciler:
 def __init__(self,dispatcher):self.dispatcher=dispatcher
 def reconcile_once(self):
  out=[]
  for r in self.dispatcher.registry.list():
   rid,desired,observed=r['runtime_id'],r['desired_state'],r['observed_state']
   if desired=='ACTIVE' and observed in {'DEFINED','STOPPED','FAILED'}:
    x=self.dispatcher.start(rid);out.append({'runtime_id':rid,'action':'START','state':x['observed_state']})
   elif desired=='ACTIVE' and observed in {'READY','DEGRADED'}:
    x=self.dispatcher.readback(rid)
    if x['observed_state']=='DEGRADED':
     x=self.dispatcher.restart(rid);out.append({'runtime_id':rid,'action':'RESTART','state':x['observed_state']})
    else:out.append({'runtime_id':rid,'action':'READBACK','state':x['observed_state']})
   elif desired=='STOPPED' and observed not in {'STOPPED','DEFINED'}:
    x=self.dispatcher.stop(rid);out.append({'runtime_id':rid,'action':'STOP','state':x['observed_state']})
  return out
