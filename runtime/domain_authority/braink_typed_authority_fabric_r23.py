from pathlib import Path
import json, sqlite3, hashlib, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT=Path('/mnt/data')
REG=ROOT/'BRAINK_R23_SERVICE_REGISTRY.sqlite'
DOMAIN='keddeh.com'
DOMAIN_ID='LEX://DOMAIN/keddeh.com'
SERVICES={
 'CLOUD':{'id':'LEX://CLOUD/BRAINK/GLOBAL','internal_mutation':True,'external_authority':'NOT_APPLICABLE'},
 'DNS':{'id':'LEX://DNS/keddeh.com','internal_mutation':True,'external_authority':'PUBLIC_DNS_NOT_GRANTED'},
 'REGISTRAR':{'id':'LEX://REGISTRAR/keddeh.com','internal_mutation':True,'external_authority':'REGISTRY_AUTHORITY_NOT_GRANTED'},
 'TLS':{'id':'LEX://TLS/keddeh.com','internal_mutation':True,'external_authority':'CA_AUTHORITY_NOT_GRANTED'},
}

def h(s): return hashlib.sha256(s.encode()).hexdigest()
def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'))

def init_registry():
    c=sqlite3.connect(REG); x=c.cursor()
    x.execute('''CREATE TABLE IF NOT EXISTS domain_services(
      domain TEXT, canonical_id TEXT, service_type TEXT, service_id TEXT,
      proof_sha256 TEXT, PRIMARY KEY(domain,service_type))''')
    x.execute('''CREATE TABLE IF NOT EXISTS carriers(
      service_id TEXT,machine_id TEXT,braink_id TEXT,lineage_id TEXT,
      vector_id TEXT,endpoint TEXT,priority INTEGER,state TEXT,
      PRIMARY KEY(service_id,machine_id))''')
    for st,info in SERVICES.items():
        proof=h(canon({'domain':DOMAIN,'canonical_id':DOMAIN_ID,'service_type':st,'service_id':info['id']}))
        x.execute('INSERT OR REPLACE INTO domain_services VALUES(?,?,?,?,?)',(DOMAIN,DOMAIN_ID,st,info['id'],proof))
        for mid,lid,vec,ep,pri in [
            ('KEX-MACHINE-001','LINEAGE::M1',f'VEC://M1/{st}/17971','http://127.0.0.1:17971',10),
            ('KEX-MACHINE-002','LINEAGE::M2',f'VEC://M2/{st}/17972','http://127.0.0.1:17972',20),
        ]:
            x.execute('INSERT OR REPLACE INTO carriers VALUES(?,?,?,?,?,?,?,?)',
                      (info['id'],mid,f'BRAINK::{mid}::R23',lid,vec,ep,pri,'ACTIVE'))
    c.commit(); c.close()

def mdb(mid): return ROOT/f'BRAINK_R23_{mid}.sqlite'
def init_machine(mid):
    c=sqlite3.connect(mdb(mid)); c.execute('''CREATE TABLE IF NOT EXISTS typed_state(
      service_type TEXT, object_key TEXT, payload_json TEXT, payload_sha256 TEXT,
      revision INTEGER, lineage_id TEXT, state TEXT, PRIMARY KEY(service_type,object_key))'''); c.commit(); c.close()

def write_state(mid,stype,key,payload,lineage,state='COMMITTED'):
    raw=canon(payload); digest=h(raw); c=sqlite3.connect(mdb(mid))
    row=c.execute('SELECT revision FROM typed_state WHERE service_type=? AND object_key=?',(stype,key)).fetchone()
    rev=(row[0] if row else 0)+1
    c.execute('INSERT OR REPLACE INTO typed_state VALUES(?,?,?,?,?,?,?)',(stype,key,raw,digest,rev,lineage,state)); c.commit(); c.close()
    return {'service_type':stype,'object_key':key,'payload':payload,'payload_sha256':digest,'revision':rev,'lineage_id':lineage,'state':state}

def overwrite_state(mid,obj,lineage,state):
    c=sqlite3.connect(mdb(mid)); c.execute('INSERT OR REPLACE INTO typed_state VALUES(?,?,?,?,?,?,?)',
      (obj['service_type'],obj['object_key'],canon(obj['payload']),obj['payload_sha256'],obj['revision'],lineage,state)); c.commit(); c.close()

def read_state(mid,stype,key):
    c=sqlite3.connect(mdb(mid)); c.row_factory=sqlite3.Row
    r=c.execute('SELECT * FROM typed_state WHERE service_type=? AND object_key=?',(stype,key)).fetchone(); c.close()
    if not r:return None
    d=dict(r); d['payload']=json.loads(d.pop('payload_json')); return d

class H(BaseHTTPRequestHandler):
    machine_id=''; lineage_id=''
    def sendj(self,status,obj):
        raw=json.dumps(obj,sort_keys=True).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=='/health': return self.sendj(200,{'status':'PASS','machine_id':self.machine_id,'braink_id':f'BRAINK::{self.machine_id}::R23','lineage_id':self.lineage_id})
        if u.path=='/state/read':
            obj=read_state(self.machine_id,q.get('service_type',[''])[0],q.get('object_key',[''])[0])
            return self.sendj(200,{'status':'PASS','machine_id':self.machine_id,'object':obj}) if obj else self.sendj(404,{'status':'NOT_FOUND'})
        return self.sendj(404,{'status':'NOT_FOUND'})
    def do_POST(self):
        u=urlparse(self.path); n=int(self.headers.get('Content-Length','0')); body=json.loads(self.rfile.read(n) or b'{}')
        if u.path!='/state/write': return self.sendj(404,{'status':'NOT_FOUND'})
        st=body['service_type']; authority=body.get('authority','INTERNAL')
        if authority!='INTERNAL':
            reason={'DNS':'PUBLIC_DNS_NOT_GRANTED','REGISTRAR':'REGISTRY_AUTHORITY_NOT_GRANTED','TLS':'CA_AUTHORITY_NOT_GRANTED','CLOUD':'EXTERNAL_AUTHORITY_NOT_APPLICABLE'}[st]
            return self.sendj(403,{'status':'BLOCKED','reason':reason})
        return self.sendj(200,{'status':'PASS','machine_id':self.machine_id,'object':write_state(self.machine_id,st,body['object_key'],body['payload'],self.lineage_id)})
    def log_message(self,*a): pass

def serve(port,mid,lid):
    cls=type(f'H_{mid}',(H,),{'machine_id':mid,'lineage_id':lid}); s=ThreadingHTTPServer(('127.0.0.1',port),cls); threading.Thread(target=s.serve_forever,daemon=True).start(); return s

def resolve(stype):
    c=sqlite3.connect(REG); c.row_factory=sqlite3.Row; d=dict(c.execute('SELECT * FROM domain_services WHERE domain=? AND service_type=?',(DOMAIN,stype)).fetchone()); rows=[dict(r) for r in c.execute("SELECT * FROM carriers WHERE service_id=? AND state='ACTIVE' ORDER BY priority",(d['service_id'],))]; c.close(); attempts=[]
    for r in rows:
        try:
            with urllib.request.urlopen(r['endpoint']+'/health',timeout=.35) as z: health=json.loads(z.read())
            if health['status']=='PASS': return {'status':'PASS','canonical_id':d['canonical_id'],'service_type':stype,'service_id':d['service_id'],'proof_sha256':d['proof_sha256'],'carrier':r,'health':health,'attempts':attempts}
        except Exception as e: attempts.append({'machine_id':r['machine_id'],'status':'FAIL','error':type(e).__name__})
    return {'status':'UNREACHABLE','canonical_id':d['canonical_id'],'service_type':stype,'service_id':d['service_id'],'attempts':attempts}

def routed_write(st,key,payload,authority='INTERNAL'):
    r=resolve(st); req=urllib.request.Request(r['carrier']['endpoint']+'/state/write',data=json.dumps({'service_type':st,'object_key':key,'payload':payload,'authority':authority}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=1) as z:return r,z.status,json.loads(z.read())
    except urllib.error.HTTPError as e:return r,e.code,json.loads(e.read())

def routed_read(st,key):
    r=resolve(st)
    with urllib.request.urlopen(r['carrier']['endpoint']+f'/state/read?service_type={st}&object_key={key}',timeout=1) as z:return r,json.loads(z.read())

def replicate(src,dst,st,key): overwrite_state(dst,read_state(src,st,key),'LINEAGE::M2' if dst.endswith('002') else 'LINEAGE::M1','REPLICA_COMMITTED')
def reconcile(src,dst,st,key): overwrite_state(dst,read_state(src,st,key),'LINEAGE::M1' if dst.endswith('001') else 'LINEAGE::M2','RECONCILED')

def main():
    init_registry(); [init_machine(mid) for mid in ('KEX-MACHINE-001','KEX-MACHINE-002')]
    s1=serve(17971,'KEX-MACHINE-001','LINEAGE::M1'); s2=serve(17972,'KEX-MACHINE-002','LINEAGE::M2'); time.sleep(.12)
    specs={'CLOUD':('cloud-object',{'value':'payload-v1'}),'DNS':('app.keddeh.com',{'authority':'INTERNAL','target':'LEX://SERVER/GLOBAL'}),'REGISTRAR':('keddeh.com',{'lock':True,'owner':'BRAINK::OWNER'}),'TLS':('keddeh.com',{'mode':'PENDING_EXTERNAL_CA','policy':'INTERNAL_ONLY'})}
    initial={}
    for st,(key,payload) in specs.items():
        route,code,res=routed_write(st,key,payload); initial[st]={'route':route,'code':code,'result':res}; replicate('KEX-MACHINE-001','KEX-MACHINE-002',st,key)
    blocked={}
    for st in ('DNS','REGISTRAR','TLS'):
        _,code,res=routed_write(st,specs[st][0],{'attempt':'external'},{'DNS':'PUBLIC','REGISTRAR':'REGISTRY','TLS':'CA'}[st]); blocked[st]={'code':code,'result':res}
    s1.shutdown(); s1.server_close(); time.sleep(.08)
    failover={st:{'route':(rr:=routed_read(st,key))[0],'result':rr[1]} for st,(key,_) in specs.items()}
    routed_write('CLOUD','cloud-object',{'value':'payload-v2'}); routed_write('DNS','app.keddeh.com',{'target':'LEX://SERVER/GLOBAL','revision':'failover'})
    s1r=serve(17971,'KEX-MACHINE-001','LINEAGE::M1'); reconcile('KEX-MACHINE-002','KEX-MACHINE-001','CLOUD','cloud-object'); reconcile('KEX-MACHINE-002','KEX-MACHINE-001','DNS','app.keddeh.com'); time.sleep(.08)
    final={st:{'m1':read_state('KEX-MACHINE-001',st,key),'m2':read_state('KEX-MACHINE-002',st,key)} for st,(key,_) in specs.items()}
    checks={'all_typed_services_initial_write':all(initial[s]['code']==200 for s in SERVICES),'all_service_ids_distinct':len({initial[s]['route']['service_id'] for s in SERVICES})==4,'canonical_domain_shared':all(initial[s]['route']['canonical_id']==DOMAIN_ID for s in SERVICES),'all_secondary_reads_after_primary_loss':all(failover[s]['result']['status']=='PASS' for s in SERVICES),'all_secondary_carriers_selected':all(failover[s]['route']['carrier']['machine_id']=='KEX-MACHINE-002' for s in SERVICES),'public_dns_blocked':blocked['DNS']['code']==403,'registry_authority_blocked':blocked['REGISTRAR']['code']==403,'ca_authority_blocked':blocked['TLS']['code']==403,'cloud_revision_advanced_on_secondary':final['CLOUD']['m2']['revision']==2,'dns_revision_advanced_on_secondary':final['DNS']['m2']['revision']==2,'cloud_reconciled_exact':final['CLOUD']['m1']['payload_sha256']==final['CLOUD']['m2']['payload_sha256'] and final['CLOUD']['m1']['revision']==final['CLOUD']['m2']['revision'],'dns_reconciled_exact':final['DNS']['m1']['payload_sha256']==final['DNS']['m2']['payload_sha256'] and final['DNS']['m1']['revision']==final['DNS']['m2']['revision'],'lineage_distinct_after_reconcile':final['CLOUD']['m1']['lineage_id']!=final['CLOUD']['m2']['lineage_id'] and final['DNS']['m1']['lineage_id']!=final['DNS']['m2']['lineage_id'],'registrar_tls_state_preserved':final['REGISTRAR']['m1']['payload_sha256']==final['REGISTRAR']['m2']['payload_sha256'] and final['TLS']['m1']['payload_sha256']==final['TLS']['m2']['payload_sha256']}
    receipt={'schema':'braink.typed-authority-fabric.r23','contract':'ONE_CANONICAL_DOMAIN_MANY_TYPED_SERVICES_WITH_INDEPENDENT_AUTHORITY_GATES','canonical_id':DOMAIN_ID,'services':SERVICES,'initial':initial,'blocked_external_mutations':blocked,'failover':failover,'final_state':final,'checks':checks,'external_authority':{'public_dns':'NOT_GRANTED','registry':'NOT_GRANTED','ca_tls':'NOT_GRANTED'},'status':'PASS' if all(checks.values()) else 'FAIL'}
    Path('/mnt/data/BRAINK_R23_TYPED_AUTHORITY_FABRIC_RECEIPT.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt,indent=2)); s1r.shutdown(); s1r.server_close(); s2.shutdown(); s2.server_close(); return 0 if receipt['status']=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
