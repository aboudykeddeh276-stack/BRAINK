from __future__ import annotations
from pathlib import Path
import sqlite3, json, hashlib, uuid, time

def sha(v):
    if isinstance(v,str):
        return hashlib.sha256(v.encode()).hexdigest()
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class MarketServiceFabric:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def db(self):
        d=sqlite3.connect(self.path); d.row_factory=sqlite3.Row
        d.execute('PRAGMA journal_mode=WAL'); d.execute('PRAGMA synchronous=FULL')
        return d
    def _init(self):
        d=self.db(); d.executescript('''
        CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,name TEXT,email TEXT,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,customer_id TEXT,name TEXT,state TEXT,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,workspace_id TEXT,path TEXT,content TEXT,content_hash TEXT,revision INTEGER,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY,customer_id TEXT,name TEXT,domain TEXT,site_type TEXT,state TEXT,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY,site_id TEXT,slug TEXT,title TEXT,body TEXT,revision INTEGER,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS roles(id TEXT PRIMARY KEY,name TEXT,scope TEXT,supervision_only INTEGER);
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY,name TEXT,role_id TEXT,state TEXT);
        CREATE TABLE IF NOT EXISTS work_modules(id TEXT PRIMARY KEY,foundry TEXT,function TEXT,instruction TEXT,state TEXT,epoch INTEGER,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS assignments(id TEXT PRIMARY KEY,work_module_id TEXT,agent_id TEXT,supervisor_id TEXT,group_name TEXT,scope TEXT,state TEXT,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS deployments(id TEXT PRIMARY KEY,business_id TEXT,server_family TEXT,replicas INTEGER,config_root TEXT,state TEXT,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,source_type TEXT,source_id TEXT,state TEXT,content_root TEXT,created_ns INTEGER);
        CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,action TEXT,target_id TEXT,status TEXT,evidence_root TEXT,created_ns INTEGER);
        '''); d.commit(); d.close()
    def receipt(self,action,target,status,evidence):
        r={'id':'RCT-'+uuid.uuid4().hex[:12],'action':action,'target_id':target,'status':status,'evidence_root':sha(evidence),'created_ns':time.time_ns()}
        d=self.db(); d.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?)',(r['id'],action,target,status,r['evidence_root'],r['created_ns'])); d.commit(); d.close()
        return r
    def create_customer(self,name,email=None):
        i='CUS-'+uuid.uuid4().hex[:12]; n=time.time_ns(); d=self.db()
        d.execute('INSERT INTO customers VALUES(?,?,?,?)',(i,name,email,n)); d.commit(); d.close()
        return {'customer_id':i,'receipt':self.receipt('create_customer',i,'PASS',{'name':name,'email':email})}
    def create_workspace(self,customer_id,name):
        i='WS-'+uuid.uuid4().hex[:12]; n=time.time_ns(); d=self.db()
        if not d.execute('SELECT 1 FROM customers WHERE id=?',(customer_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_CUSTOMER')
        d.execute('INSERT INTO workspaces VALUES(?,?,?,?,?)',(i,customer_id,name,'ACTIVE',n)); d.commit(); d.close()
        return {'workspace_id':i,'receipt':self.receipt('create_workspace',i,'PASS',{'customer_id':customer_id,'name':name})}
    def write_artifact(self,workspace_id,path,content):
        d=self.db()
        if not d.execute('SELECT 1 FROM workspaces WHERE id=?',(workspace_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_WORKSPACE')
        rev=d.execute('SELECT MAX(revision) FROM artifacts WHERE workspace_id=? AND path=?',(workspace_id,path)).fetchone()[0] or 0
        i='ART-'+uuid.uuid4().hex[:12]; n=time.time_ns(); h=sha(content)
        d.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)',(i,workspace_id,path,content,h,rev+1,n)); d.commit(); d.close()
        return {'artifact_id':i,'revision':rev+1,'sha256':h,'receipt':self.receipt('write_artifact',i,'PASS',{'workspace_id':workspace_id,'path':path,'revision':rev+1,'sha256':h})}
    def create_site(self,customer_id,name,domain,site_type='WEBSITE'):
        i='SITE-'+uuid.uuid4().hex[:12]; n=time.time_ns(); d=self.db()
        if not d.execute('SELECT 1 FROM customers WHERE id=?',(customer_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_CUSTOMER')
        d.execute('INSERT INTO sites VALUES(?,?,?,?,?,?,?)',(i,customer_id,name,domain,site_type,'DRAFT',n)); d.commit(); d.close()
        return {'site_id':i,'state':'DRAFT','receipt':self.receipt('create_site',i,'PASS',{'domain':domain,'site_type':site_type})}
    def put_page(self,site_id,slug,title,body):
        d=self.db()
        if not d.execute('SELECT 1 FROM sites WHERE id=?',(site_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_SITE')
        rev=d.execute('SELECT MAX(revision) FROM pages WHERE site_id=? AND slug=?',(site_id,slug)).fetchone()[0] or 0
        i='PAGE-'+uuid.uuid4().hex[:12]; n=time.time_ns()
        d.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',(i,site_id,slug,title,body,rev+1,n)); d.commit(); d.close()
        return {'page_id':i,'revision':rev+1,'receipt':self.receipt('put_page',i,'PASS',{'site_id':site_id,'slug':slug,'revision':rev+1})}
    def publish_site(self,site_id):
        d=self.db()
        rows=d.execute('SELECT slug,title,body,revision FROM pages WHERE site_id=? ORDER BY slug,revision',(site_id,)).fetchall()
        latest={}
        for r in rows: latest[r['slug']]={'slug':r['slug'],'title':r['title'],'body':r['body'],'revision':r['revision']}
        if not latest: d.close(); raise ValueError('NO_PAGES')
        payload={'site_id':site_id,'pages':latest}; cr=sha(payload); pid='PUB-'+uuid.uuid4().hex[:12]; n=time.time_ns()
        d.execute('INSERT INTO publications VALUES(?,?,?,?,?,?)',(pid,'SITE',site_id,'QUALIFIED_LOCAL',cr,n))
        d.execute("UPDATE sites SET state='QUALIFIED_LOCAL' WHERE id=?",(site_id,)); d.commit(); d.close()
        return {'publication_id':pid,'state':'QUALIFIED_LOCAL','content_root':cr,'page_count':len(latest),'receipt':self.receipt('publish_site',site_id,'PASS',{'publication_id':pid,'content_root':cr})}
    def register_role(self,name,scope,supervision_only=False):
        i='ROLE-'+uuid.uuid4().hex[:12]; d=self.db()
        d.execute('INSERT INTO roles VALUES(?,?,?,?)',(i,name,scope,1 if supervision_only else 0)); d.commit(); d.close()
        return {'role_id':i,'receipt':self.receipt('register_role',i,'PASS',{'name':name,'scope':scope,'supervision_only':supervision_only})}
    def register_agent(self,name,role_id):
        i='AGENT-'+uuid.uuid4().hex[:12]; d=self.db()
        if not d.execute('SELECT 1 FROM roles WHERE id=?',(role_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_ROLE')
        d.execute('INSERT INTO agents VALUES(?,?,?,?)',(i,name,role_id,'ACTIVE')); d.commit(); d.close()
        return {'agent_id':i,'receipt':self.receipt('register_agent',i,'PASS',{'name':name,'role_id':role_id})}
    def create_work_module(self,foundry,function,instruction):
        i='WM-'+sha({'foundry':foundry,'function':function,'instruction':instruction,'nonce':uuid.uuid4().hex})[:16]
        n=time.time_ns(); d=self.db()
        d.execute('INSERT INTO work_modules VALUES(?,?,?,?,?,?,?)',(i,foundry,function,instruction,'READY',1,n)); d.commit(); d.close()
        return {'work_module_id':i,'receipt':self.receipt('create_work_module',i,'PASS',{'foundry':foundry,'function':function})}
    def assign_agent(self,work_module_id,agent_id,supervisor_id,group_name,scope):
        i='ASN-'+uuid.uuid4().hex[:12]; n=time.time_ns(); d=self.db()
        if not d.execute('SELECT 1 FROM work_modules WHERE id=?',(work_module_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_WORK_MODULE')
        if not d.execute('SELECT 1 FROM agents WHERE id=?',(agent_id,)).fetchone():
            d.close(); raise ValueError('UNKNOWN_AGENT')
        d.execute('INSERT INTO assignments VALUES(?,?,?,?,?,?,?,?)',(i,work_module_id,agent_id,supervisor_id,group_name,scope,'ASSIGNED',n)); d.commit(); d.close()
        return {'assignment_id':i,'receipt':self.receipt('assign_agent',i,'PASS',{'work_module_id':work_module_id,'agent_id':agent_id,'scope':scope})}
    def deploy_server_set(self,business_id,server_family,replicas,config):
        i='DEP-'+uuid.uuid4().hex[:12]; n=time.time_ns(); cr=sha(config); d=self.db()
        d.execute('INSERT INTO deployments VALUES(?,?,?,?,?,?,?)',(i,business_id,server_family,int(replicas),cr,'CONFIGURED_LOCAL',n)); d.commit(); d.close()
        return {'deployment_id':i,'state':'CONFIGURED_LOCAL','config_root':cr,'receipt':self.receipt('deploy_server_set',i,'PASS',{'business_id':business_id,'server_family':server_family,'replicas':replicas,'config_root':cr})}
    def metrics(self):
        d=self.db(); tables=('customers','workspaces','artifacts','sites','pages','roles','agents','work_modules','assignments','deployments','publications','receipts')
        out={t:d.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tables}; d.close(); out['state_root']=sha(out); return out
