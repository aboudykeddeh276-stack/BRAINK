#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sqlite3,time,uuid
from pathlib import Path
def canon(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(v): return hashlib.sha256(canon(v).encode()).hexdigest()
SCHEMA='''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS templates(template_id TEXT,version INTEGER,semantic_type TEXT,node_class TEXT,definition TEXT,input_schema TEXT,output_schema TEXT,attributes TEXT,capabilities TEXT,integration_contracts TEXT,state_schema TEXT,observer_contract TEXT,attribution_graph TEXT,template_hash TEXT,created_ns INTEGER,PRIMARY KEY(template_id,version));
CREATE TABLE IF NOT EXISTS instances(instance_id TEXT PRIMARY KEY,template_id TEXT,template_version INTEGER,lineage_hash TEXT,state TEXT,observer_id TEXT,vfs_uri TEXT,runtime_uri TEXT,network_uri TEXT,attributes TEXT,attribution_graph TEXT,created_ns INTEGER,updated_ns INTEGER,FOREIGN KEY(template_id,template_version) REFERENCES templates(template_id,version));
CREATE TABLE IF NOT EXISTS edges(edge_id TEXT PRIMARY KEY,source_id TEXT,target_id TEXT,relation TEXT,attributes TEXT,attribution TEXT,created_ns INTEGER);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,ts_ns INTEGER,actor TEXT,subject_id TEXT,action TEXT,state TEXT,evidence TEXT,prev_hash TEXT,event_hash TEXT);'''
class NodeFabric:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row;self.db.executescript(SCHEMA)
 def event(self,subject,action,state,evidence,actor='BRAINK_NODE_FABRIC'):
  r=self.db.execute('SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1').fetchone();prev=r[0] if r else 'GENESIS';ts=time.time_ns();body={'ts_ns':ts,'actor':actor,'subject_id':subject,'action':action,'state':state,'evidence':evidence,'prev_hash':prev};eh=digest(body);self.db.execute('INSERT INTO events(ts_ns,actor,subject_id,action,state,evidence,prev_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)',(ts,actor,subject,action,state,canon(evidence),prev,eh));self.db.commit();return eh
 def define(self,spec):
  required=['template_id','semantic_type','node_class','definition','input_schema','output_schema','attributes','capabilities','integration_contracts','state_schema','observer_contract','attribution_graph'];missing=[x for x in required if x not in spec]
  if missing: raise ValueError('missing:'+','.join(missing))
  if spec['node_class'] not in {'DUMB','SMART'}: raise ValueError('node_class')
  version=self.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM templates WHERE template_id=?',(spec['template_id'],)).fetchone()[0];payload={k:spec[k] for k in required};payload['version']=version;th=digest(payload);ts=time.time_ns()
  self.db.execute('INSERT INTO templates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(spec['template_id'],version,spec['semantic_type'],spec['node_class'],canon(spec['definition']),canon(spec['input_schema']),canon(spec['output_schema']),canon(spec['attributes']),canon(spec['capabilities']),canon(spec['integration_contracts']),canon(spec['state_schema']),canon(spec['observer_contract']),canon(spec['attribution_graph']),th,ts));self.db.commit();self.event(spec['template_id'],'TEMPLATE_DEFINE','COMMITTED',{'version':version,'template_hash':th});return self.template(spec['template_id'],version)
 def template(self,tid,version=None):
  q='SELECT * FROM templates WHERE template_id=? '+('AND version=?' if version else 'ORDER BY version DESC LIMIT 1');args=(tid,version) if version else (tid,);r=self.db.execute(q,args).fetchone();return self._decode(r) if r else None
 def instantiate(self,tid,version=None,attributes=None,attribution=None,state=None):
  t=self.template(tid,version)
  if not t: raise KeyError(tid)
  iid='node_'+uuid.uuid4().hex;obs='observer://'+iid;vfs='vfs://node/'+iid;runtime='runtime://node/'+iid;network='network://node/'+iid;lineage=digest({'template_id':tid,'template_version':t['version'],'template_hash':t['template_hash'],'instance_id':iid});ts=time.time_ns();attrs={**t['attributes'],**(attributes or {})};attrgraph=t['attribution_graph']+(attribution or []);st=state if state is not None else t['state_schema'].get('default',{})
  self.db.execute('INSERT INTO instances VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,tid,t['version'],lineage,canon(st),obs,vfs,runtime,network,canon(attrs),canon(attrgraph),ts,ts));self.db.commit();self.event(iid,'INSTANTIATE','COMMITTED',{'template_id':tid,'template_version':t['version'],'lineage_hash':lineage,'observer_id':obs,'vfs_uri':vfs,'runtime_uri':runtime,'network_uri':network});return self.instance(iid)
 def instance(self,iid):
  r=self.db.execute('SELECT * FROM instances WHERE instance_id=?',(iid,)).fetchone();return self._decode(r) if r else None
 def connect(self,source,target,relation,attributes=None,attribution=None):
  if not (self.instance(source) or self.template(source)): raise KeyError(source)
  if not (self.instance(target) or self.template(target)): raise KeyError(target)
  eid='edge_'+uuid.uuid4().hex;ev={'source':source,'target':target,'relation':relation,'attributes':attributes or {},'attribution':attribution or []};self.db.execute('INSERT INTO edges VALUES(?,?,?,?,?,?,?)',(eid,source,target,relation,canon(attributes or {}),canon(attribution or []),time.time_ns()));self.db.commit();self.event(eid,'EDGE_BIND','COMMITTED',ev);return {'edge_id':eid,**ev}
 def set_state(self,iid,state,observer_id):
  n=self.instance(iid)
  if not n: raise KeyError(iid)
  if observer_id!=n['observer_id']: raise PermissionError('observer mismatch')
  self.db.execute('UPDATE instances SET state=?,updated_ns=? WHERE instance_id=?',(canon(state),time.time_ns(),iid));self.db.commit();self.event(iid,'STATE_TRANSITION','COMMITTED',{'observer_id':observer_id,'state_hash':digest(state)});return self.instance(iid)
 def export_graph(self):
  return {'schema':'braink.kex.node-fabric.v1','templates':[self._decode(x) for x in self.db.execute('SELECT * FROM templates ORDER BY template_id,version')],'instances':[self._decode(x) for x in self.db.execute('SELECT * FROM instances ORDER BY instance_id')],'edges':[self._decode(x) for x in self.db.execute('SELECT * FROM edges ORDER BY edge_id')],'ledger':self.verify()}
 def verify(self):
  prev='GENESIS';count=0
  for r in self.db.execute('SELECT * FROM events ORDER BY seq'):
   body={'ts_ns':r['ts_ns'],'actor':r['actor'],'subject_id':r['subject_id'],'action':r['action'],'state':r['state'],'evidence':json.loads(r['evidence']),'prev_hash':r['prev_hash']};expected=digest(body)
   if r['prev_hash']!=prev or expected!=r['event_hash']:return {'ok':False,'seq':r['seq']}
   prev=r['event_hash'];count+=1
  return {'ok':True,'count':count,'head':prev}
 def _decode(self,r):
  if not r:return None
  d=dict(r)
  for k in ['definition','input_schema','output_schema','attributes','capabilities','integration_contracts','state_schema','observer_contract','attribution_graph','state','attribution']:
   if k in d and isinstance(d[k],str):
    try:d[k]=json.loads(d[k])
    except:pass
  return d
