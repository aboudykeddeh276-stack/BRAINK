#!/usr/bin/env python3
from __future__ import annotations
import sqlite3, json, hashlib, secrets, datetime as dt, re, os, base64
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parent
DB_PATH=Path(os.environ.get('KEDDEH_REGISTRAR_DB', ROOT/'state/registrar.sqlite3'))
UTC=dt.timezone.utc
DOM_RE=re.compile(r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$', re.I)
HOST_RE=DOM_RE
IP_RE=re.compile(r'^[0-9a-fA-F:.]+$')

PORTFOLIO=[
 ('keddeh.com',18.90,'AUD','KEX://DOMAIN-SPACE/keddeh'),
 ('claimpath.org',12.15,'AUD','KEX://DOMAIN-SPACE/claimpath'),
 ('braink.com.au',18.90,'AUD','KEX://DOMAIN-SPACE/braink-au'),
 ('braink.store',6.00,'AUD','KEX://DOMAIN-SPACE/braink-store'),
 ('braink.studio',None,'AUD','KEX://DOMAIN-SPACE/braink-studio'),
]
REGISTRY_PROFILES={
 'com':{'family':'GTLD','adapter':'EPP_RFC5730','authority':'ICANN_ACCREDITATION_AND_REGISTRY_RRA','rdap':'ICANN_PROFILE'},
 'org':{'family':'GTLD','adapter':'EPP_RFC5730','authority':'ICANN_ACCREDITATION_AND_REGISTRY_RRA','rdap':'ICANN_PROFILE'},
 'store':{'family':'GTLD','adapter':'EPP_RFC5730','authority':'ICANN_ACCREDITATION_AND_REGISTRY_RRA','rdap':'ICANN_PROFILE'},
 'studio':{'family':'GTLD','adapter':'EPP_RFC5730','authority':'ICANN_ACCREDITATION_AND_REGISTRY_RRA','rdap':'ICANN_PROFILE'},
 'com.au':{'family':'AU','adapter':'EPP_AU_REGISTRY','authority':'AUDA_ACCREDITATION_AND_REGISTRY_RRA','rdap':'AU_PROFILE'},
}
TERRITORY={
 'identity':'KEX://FLOW/REGISTRAR/100TB','declared_capacity':'100TB',
 'capacity_semantics':'LOGICAL_ROUTE_PRESERVED_TERRITORY','physical_allocation_claimed':False,
 'failure_domain':'REGISTRAR_TERRITORY_1','lineage_root':'KEXSSD-1000TB-HEXxHEX-DNA-ROOT-008',
 'lanes':[
  {'id':'R01','name':'REGISTRATION_OBJECTS','declared_share':'10TB'},
  {'id':'R02','name':'CONTACTS_PRIVACY','declared_share':'10TB'},
  {'id':'R03','name':'HOST_GLUE','declared_share':'10TB'},
  {'id':'R04','name':'DNSSEC_DELEGATION','declared_share':'10TB'},
  {'id':'R05','name':'REGISTRY_TRANSACTIONS','declared_share':'10TB'},
  {'id':'R06','name':'RDAP_PUBLICATION','declared_share':'10TB'},
  {'id':'R07','name':'BILLING_RENEWAL','declared_share':'10TB'},
  {'id':'R08','name':'TRANSFER_LIFECYCLE','declared_share':'10TB'},
  {'id':'R09','name':'ESCROW_AUDIT_PROOF','declared_share':'10TB'},
  {'id':'R10','name':'RECOVERY_REHYDRATION','declared_share':'10TB'},
 ]}

def now(): return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def canon(o): return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha_bytes(b:bytes): return hashlib.sha256(b).hexdigest()
def sha_obj(o): return sha_bytes(canon(o).encode())
def fqdn(name):
 n=str(name).strip().lower().rstrip('.')
 if not DOM_RE.match(n): raise ValueError('INVALID_DOMAIN')
 return n

def tld_key(domain:str)->str:
 d=fqdn(domain); return 'com.au' if d.endswith('.com.au') else d.rsplit('.',1)[1]
def registry_profile(domain):
 k=tld_key(domain)
 if k not in REGISTRY_PROFILES: raise ValueError('UNSUPPORTED_REGISTRY_PROFILE')
 return REGISTRY_PROFILES[k]

def _json(v): return json.loads(v) if isinstance(v,str) else v

def _epp_text(tag, text, ns=None):
 e=ET.Element(tag if ns is None else f'{{{ns}}}{tag}'); e.text=str(text); return e

class Registrar:
 def __init__(self,path:Path=DB_PATH):
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
  self.db=sqlite3.connect(self.path, timeout=30); self.db.row_factory=sqlite3.Row
  self.db.execute('PRAGMA foreign_keys=ON'); self.db.execute('PRAGMA journal_mode=WAL')
  self.init_schema(); self.seed()
 def close(self): self.db.close()
 def init_schema(self):
  self.db.executescript('''
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,name TEXT NOT NULL,org TEXT,email TEXT NOT NULL,phone TEXT,address_json TEXT NOT NULL,privacy TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS domains(name TEXT PRIMARY KEY,local_state TEXT NOT NULL,registry_state TEXT NOT NULL,registrant_id TEXT,admin_id TEXT,tech_id TEXT,billing_id TEXT,auth_info_hash TEXT NOT NULL,local_acquired_at TEXT,registry_created_at TEXT,registry_expires_at TEXT,updated_at TEXT NOT NULL,auto_renew INTEGER NOT NULL DEFAULT 1,locked INTEGER NOT NULL DEFAULT 1,privacy TEXT NOT NULL DEFAULT 'REDACTED_PUBLIC',purchase_price REAL,currency TEXT,kex_coordinate TEXT,registry_profile TEXT NOT NULL,sponsor_registrar TEXT,registry_object_id TEXT,FOREIGN KEY(registrant_id) REFERENCES contacts(id));
CREATE TABLE IF NOT EXISTS hosts(name TEXT PRIMARY KEY,domain TEXT NOT NULL,addresses_json TEXT NOT NULL,registry_state TEXT NOT NULL DEFAULT 'LOCAL_ONLY',registry_object_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(domain) REFERENCES domains(name) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS nameservers(domain TEXT NOT NULL,host TEXT NOT NULL,ordinal INTEGER NOT NULL,PRIMARY KEY(domain,host),FOREIGN KEY(domain) REFERENCES domains(name) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS ds_records(domain TEXT NOT NULL,key_tag INTEGER NOT NULL,algorithm INTEGER NOT NULL,digest_type INTEGER NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(domain,key_tag,algorithm,digest_type),FOREIGN KEY(domain) REFERENCES domains(name) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,domain TEXT NOT NULL,kind TEXT NOT NULL,amount REAL,currency TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,settled_at TEXT,external_ref TEXT,FOREIGN KEY(domain) REFERENCES domains(name));
CREATE TABLE IF NOT EXISTS transfers(id TEXT PRIMARY KEY,domain TEXT NOT NULL,direction TEXT NOT NULL,status TEXT NOT NULL,requested_at TEXT NOT NULL,updated_at TEXT NOT NULL,token_hash TEXT NOT NULL,registry_queue_id TEXT,FOREIGN KEY(domain) REFERENCES domains(name));
CREATE TABLE IF NOT EXISTS registry_queue(id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE NOT NULL,domain TEXT,object_type TEXT NOT NULL,operation TEXT NOT NULL,payload_json TEXT NOT NULL,state TEXT NOT NULL,required_authority TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,result_json TEXT,attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS registry_receipts(id TEXT PRIMARY KEY,queue_id TEXT NOT NULL,registry_transaction TEXT,result_json TEXT NOT NULL,observed_at TEXT NOT NULL,result_hash TEXT NOT NULL,FOREIGN KEY(queue_id) REFERENCES registry_queue(id));
CREATE TABLE IF NOT EXISTS agreements(id TEXT PRIMARY KEY,kind TEXT NOT NULL,scope TEXT NOT NULL,state TEXT NOT NULL,effective_at TEXT,expires_at TEXT,evidence_ref TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,subject TEXT NOT NULL,payload_json TEXT NOT NULL,previous_hash TEXT,entry_hash TEXT NOT NULL,created_at TEXT NOT NULL);
'''); self.db.commit()
 def audit(self,event,subject,payload):
  prev=self.db.execute('SELECT entry_hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone(); ph=prev['entry_hash'] if prev else None
  core={'event':event,'subject':subject,'payload':payload,'previous_hash':ph,'created_at':now()}; h=sha_obj(core)
  self.db.execute('INSERT INTO audit(event,subject,payload_json,previous_hash,entry_hash,created_at) VALUES(?,?,?,?,?,?)',(event,subject,canon(payload),ph,h,core['created_at'])); self.db.commit(); return h
 def seed(self):
  self.db.execute('INSERT OR IGNORE INTO meta(k,v) VALUES(?,?)',('territory',canon(TERRITORY)))
  self.db.execute('INSERT OR IGNORE INTO meta(k,v) VALUES(?,?)',('service_identity','registrar://keddeh/sovereign/v2'))
  cid='CONTACT-KEDDEH-OWNER'; ts=now()
  self.db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?,?,?,?,?,?,?,?)',(cid,'KEDDEH DOMAIN OWNER','KEDDEH Systems','owner@localhost.invalid','',canon({}),'PRIVATE_INTERNAL',ts,ts))
  for name,price,curr,coord in PORTFOLIO:
   self.db.execute('''INSERT OR IGNORE INTO domains(name,local_state,registry_state,registrant_id,admin_id,tech_id,billing_id,auth_info_hash,local_acquired_at,registry_created_at,registry_expires_at,updated_at,auto_renew,locked,privacy,purchase_price,currency,kex_coordinate,registry_profile,sponsor_registrar,registry_object_id)
   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(name,'LOCAL_ACQUISITION_RECORDED','UNOBSERVED_REGISTRY',cid,cid,cid,cid,sha_obj({'seed':name,'nonce':secrets.token_hex(16)}),ts,None,None,ts,1,1,'REDACTED_PUBLIC',price,curr,coord,tld_key(name),None,None))
  for kind,scope in [('ICANN_RAA','GTLD'),('REGISTRY_RRA_COM','com'),('REGISTRY_RRA_ORG','org'),('REGISTRY_RRA_STORE','store'),('REGISTRY_RRA_STUDIO','studio'),('AUDA_REGISTRAR_AGREEMENT','AU'),('AU_REGISTRY_RRA','com.au'),('REGISTRAR_DATA_ESCROW','GTLD')]:
   self.db.execute('INSERT OR IGNORE INTO agreements VALUES(?,?,?,?,?,?,?,?)',('AGR-'+kind,kind,scope,'UNBOUND',None,None,None,ts))
  self.db.commit()
 def list_domains(self): return [dict(r) for r in self.db.execute('SELECT * FROM domains ORDER BY name')]
 def get_domain(self,name):
  n=fqdn(name); r=self.db.execute('SELECT * FROM domains WHERE name=?',(n,)).fetchone()
  if not r:return None
  o=dict(r); o['nameservers']=[dict(x) for x in self.db.execute('SELECT * FROM nameservers WHERE domain=? ORDER BY ordinal,host',(n,))]; o['ds']=[dict(x) for x in self.db.execute('SELECT * FROM ds_records WHERE domain=? ORDER BY key_tag',(n,))]; o['hosts']=[{**dict(x),'addresses':_json(x['addresses_json'])} for x in self.db.execute('SELECT * FROM hosts WHERE domain=? ORDER BY name',(n,))]; return o
 def set_registry_observation(self,domain, *, created_at=None, expires_at=None, sponsor=None, registry_object_id=None, evidence_ref=None):
  n=fqdn(domain); self._must_domain(n); ts=now()
  self.db.execute('UPDATE domains SET registry_state=?,registry_created_at=?,registry_expires_at=?,sponsor_registrar=?,registry_object_id=?,updated_at=? WHERE name=?',('REGISTRY_OBSERVED',created_at,expires_at,sponsor,registry_object_id,ts,n)); self.db.commit(); self.audit('REGISTRY_OBSERVATION_IMPORT',n,{'created_at':created_at,'expires_at':expires_at,'sponsor':sponsor,'registry_object_id':registry_object_id,'evidence_ref':evidence_ref})
 def create_contact(self,p):
  cid=p.get('id') or 'C-'+secrets.token_hex(8).upper(); ts=now(); email=str(p['email']).strip().lower()
  self.db.execute('INSERT INTO contacts VALUES(?,?,?,?,?,?,?,?,?)',(cid,p['name'],p.get('org',''),email,p.get('phone',''),canon(p.get('address',{})),p.get('privacy','PRIVATE_INTERNAL'),ts,ts)); self.db.commit(); self.audit('CONTACT_CREATE',cid,{'privacy':p.get('privacy','PRIVATE_INTERNAL')}); return cid
 def set_contact_roles(self,domain,**roles):
  n=fqdn(domain); self._must_domain(n); allowed={'registrant_id','admin_id','tech_id','billing_id'}
  for k,v in roles.items():
   if k not in allowed: raise ValueError('INVALID_CONTACT_ROLE')
   if not self.db.execute('SELECT 1 FROM contacts WHERE id=?',(v,)).fetchone(): raise KeyError('CONTACT_NOT_FOUND')
   self.db.execute(f'UPDATE domains SET {k}=?,updated_at=? WHERE name=?',(v,now(),n))
  self.db.commit(); self.audit('DOMAIN_CONTACTS_UPDATE',n,roles); return self.queue(n,'domain','update_contacts',roles)
 def set_nameservers(self,domain,hosts):
  n=fqdn(domain); self._must_domain(n); norm=[]
  for h in hosts:
   h=fqdn(h)
   if h not in norm:norm.append(h)
  if len(norm)<2: raise ValueError('MINIMUM_TWO_NAMESERVERS')
  self.db.execute('DELETE FROM nameservers WHERE domain=?',(n,))
  for i,h in enumerate(norm,1): self.db.execute('INSERT INTO nameservers VALUES(?,?,?)',(n,h,i))
  self.db.execute('UPDATE domains SET updated_at=? WHERE name=?',(now(),n)); self.db.commit(); self.audit('NAMESERVERS_UPDATE',n,{'hosts':norm}); return self.queue(n,'domain','update_nameservers',{'nameservers':norm})
 def upsert_host(self,domain,host,addresses):
  n=fqdn(domain); h=fqdn(host); self._must_domain(n); ts=now(); addrs=[]
  for a in addresses:
   a=str(a).strip()
   if not IP_RE.match(a): raise ValueError('INVALID_IP_LITERAL')
   if a not in addrs:addrs.append(a)
  self.db.execute('''INSERT INTO hosts(name,domain,addresses_json,registry_state,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET domain=excluded.domain,addresses_json=excluded.addresses_json,updated_at=excluded.updated_at''',(h,n,canon(addrs),'LOCAL_ONLY',ts,ts)); self.db.commit(); self.audit('HOST_UPSERT',h,{'domain':n,'addresses':addrs}); return self.queue(n,'host','upsert_host',{'host':h,'addresses':addrs})
 def set_ds(self,domain,records):
  n=fqdn(domain); self._must_domain(n); clean=[]; self.db.execute('DELETE FROM ds_records WHERE domain=?',(n,))
  for r in records:
   d={'key_tag':int(r['key_tag']),'algorithm':int(r['algorithm']),'digest_type':int(r['digest_type']),'digest':str(r['digest']).upper()}
   if not re.fullmatch(r'[0-9A-F]+',d['digest']) or len(d['digest'])%2: raise ValueError('INVALID_DS_DIGEST')
   clean.append(d); self.db.execute('INSERT INTO ds_records VALUES(?,?,?,?,?)',(n,d['key_tag'],d['algorithm'],d['digest_type'],d['digest']))
  self.db.commit(); self.audit('DS_UPDATE',n,{'records':clean}); return self.queue(n,'domain','update_ds',{'ds':clean})
 def renew(self,domain,years=1,amount=None,currency='AUD'):
  n=fqdn(domain); d=self._must_domain(n); years=int(years)
  if years<1 or years>10: raise ValueError('INVALID_RENEW_PERIOD')
  ts=now(); oid='ORD-'+secrets.token_hex(8).upper(); self.db.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)',(oid,n,'RENEW',amount,currency,'COMMITTED_LOCAL',ts,ts,None)); self.db.commit(); self.audit('DOMAIN_RENEW_INTENT',n,{'years':years,'order_id':oid,'known_registry_expiry':d['registry_expires_at']}); return {'order_id':oid,'registry_queue_id':self.queue(n,'domain','renew',{'years':years,'current_expiry':d['registry_expires_at']})}
 def set_lock(self,domain,locked:bool):
  n=fqdn(domain); self._must_domain(n); self.db.execute('UPDATE domains SET locked=?,updated_at=? WHERE name=?',(1 if locked else 0,now(),n)); self.db.commit(); self.audit('DOMAIN_LOCK',n,{'locked':bool(locked)}); return self.queue(n,'domain','set_lock',{'locked':bool(locked)})
 def transfer(self,domain,direction='OUT'):
  n=fqdn(domain); self._must_domain(n); direction=str(direction).upper();
  if direction not in {'IN','OUT'}: raise ValueError('INVALID_TRANSFER_DIRECTION')
  token=secrets.token_urlsafe(32); tid='XFR-'+secrets.token_hex(8).upper(); ts=now(); q=self.queue(n,'domain','transfer_request',{'direction':direction,'transfer_id':tid})
  self.db.execute('INSERT INTO transfers VALUES(?,?,?,?,?,?,?,?)',(tid,n,direction,'REQUESTED',ts,ts,sha_obj(token),q)); self.db.commit(); self.audit('TRANSFER_REQUEST',n,{'id':tid,'direction':direction,'registry_queue_id':q}); return {'id':tid,'auth_info':token,'registry_queue_id':q}
 def queue(self,domain,obj,op,payload):
  n=fqdn(domain); profile=registry_profile(n); stable={'domain':n,'object_type':obj,'operation':op,'payload':payload}; idem=sha_obj(stable)
  existing=self.db.execute('SELECT id FROM registry_queue WHERE idempotency_key=?',(idem,)).fetchone()
  if existing:return existing['id']
  qid='REG-'+secrets.token_hex(10).upper(); ts=now(); self.db.execute('INSERT INTO registry_queue(id,idempotency_key,domain,object_type,operation,payload_json,state,required_authority,created_at,updated_at,result_json,attempts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(qid,idem,n,obj,op,canon(payload),'AWAITING_REGISTRY_AUTHORITY',profile['authority'],ts,ts,None,0)); self.db.commit(); self.audit('REGISTRY_INTENT',n,{'id':qid,'object':obj,'operation':op,'idempotency_key':idem}); return qid
 def queue_list(self): return [dict(r) for r in self.db.execute('SELECT * FROM registry_queue ORDER BY created_at DESC,id DESC')]
 def acknowledge_registry(self,qid,result):
  r=self.db.execute('SELECT * FROM registry_queue WHERE id=?',(qid,)).fetchone()
  if not r: raise KeyError('QUEUE_NOT_FOUND')
  state='COMPLETED' if bool(result.get('success')) else 'FAILED'; ts=now(); rid='RCP-'+secrets.token_hex(8).upper(); rh=sha_obj(result)
  self.db.execute('UPDATE registry_queue SET state=?,updated_at=?,result_json=?,attempts=attempts+1 WHERE id=?',(state,ts,canon(result),qid))
  self.db.execute('INSERT INTO registry_receipts VALUES(?,?,?,?,?,?)',(rid,qid,result.get('registry_transaction'),canon(result),ts,rh))
  if r['domain'] and state=='COMPLETED':
   expiry=result.get('expires_at'); created=result.get('created_at'); sponsor=result.get('sponsor_registrar'); object_id=result.get('registry_object_id')
   self.db.execute('''UPDATE domains SET registry_state='REGISTRY_CONFIRMED',registry_created_at=COALESCE(?,registry_created_at),registry_expires_at=COALESCE(?,registry_expires_at),sponsor_registrar=COALESCE(?,sponsor_registrar),registry_object_id=COALESCE(?,registry_object_id),updated_at=? WHERE name=?''',(created,expiry,sponsor,object_id,ts,r['domain']))
  self.db.commit(); self.audit('REGISTRY_READBACK',r['domain'] or qid,{'id':qid,'receipt_id':rid,'state':state,'result_hash':rh}); return {'state':state,'receipt_id':rid,'result_hash':rh}
 def bind_agreement(self,agreement_id,state,evidence_ref=None,effective_at=None,expires_at=None):
  r=self.db.execute('SELECT * FROM agreements WHERE id=?',(agreement_id,)).fetchone()
  if not r: raise KeyError('AGREEMENT_NOT_FOUND')
  self.db.execute('UPDATE agreements SET state=?,evidence_ref=?,effective_at=?,expires_at=?,updated_at=? WHERE id=?',(state,evidence_ref,effective_at,expires_at,now(),agreement_id)); self.db.commit(); self.audit('AGREEMENT_BIND',agreement_id,{'state':state,'evidence_ref':evidence_ref}); return dict(self.db.execute('SELECT * FROM agreements WHERE id=?',(agreement_id,)).fetchone())
 def agreements(self): return [dict(r) for r in self.db.execute('SELECT * FROM agreements ORDER BY scope,kind')]
 def epp_xml(self,qid):
  r=self.db.execute('SELECT * FROM registry_queue WHERE id=?',(qid,)).fetchone()
  if not r: raise KeyError('QUEUE_NOT_FOUND')
  p=_json(r['payload_json']); d=r['domain']; op=r['operation']; EPP='urn:ietf:params:xml:ns:epp-1.0'; DNS='urn:ietf:params:xml:ns:domain-1.0'; HNS='urn:ietf:params:xml:ns:host-1.0'; SNS='urn:ietf:params:xml:ns:secDNS-1.1'
  ET.register_namespace('',EPP); ET.register_namespace('domain',DNS); ET.register_namespace('host',HNS); ET.register_namespace('secDNS',SNS)
  root=ET.Element(f'{{{EPP}}}epp'); cmd=ET.SubElement(root,f'{{{EPP}}}command')
  if op=='renew':
   c=ET.SubElement(cmd,f'{{{EPP}}}renew'); x=ET.SubElement(c,f'{{{DNS}}}renew'); ET.SubElement(x,f'{{{DNS}}}name').text=d
   if p.get('current_expiry'): ET.SubElement(x,f'{{{DNS}}}curExpDate').text=str(p['current_expiry'])[:10]
   q=ET.SubElement(x,f'{{{DNS}}}period',{'unit':'y'}); q.text=str(int(p.get('years',1)))
  elif op=='update_nameservers':
   c=ET.SubElement(cmd,f'{{{EPP}}}update'); x=ET.SubElement(c,f'{{{DNS}}}update'); ET.SubElement(x,f'{{{DNS}}}name').text=d; add=ET.SubElement(x,f'{{{DNS}}}add'); ns=ET.SubElement(add,f'{{{DNS}}}ns')
   for h in p['nameservers']: ET.SubElement(ns,f'{{{DNS}}}hostObj').text=h
  elif op=='set_lock':
   c=ET.SubElement(cmd,f'{{{EPP}}}update'); x=ET.SubElement(c,f'{{{DNS}}}update'); ET.SubElement(x,f'{{{DNS}}}name').text=d; box=ET.SubElement(x,f'{{{DNS}}}{"add" if p["locked"] else "rem"}'); ET.SubElement(box,f'{{{DNS}}}status',{'s':'clientTransferProhibited'})
  elif op=='transfer_request':
   c=ET.SubElement(cmd,f'{{{EPP}}}transfer',{'op':'request'}); x=ET.SubElement(c,f'{{{DNS}}}transfer'); ET.SubElement(x,f'{{{DNS}}}name').text=d
  elif op=='upsert_host':
   c=ET.SubElement(cmd,f'{{{EPP}}}create'); x=ET.SubElement(c,f'{{{HNS}}}create'); ET.SubElement(x,f'{{{HNS}}}name').text=p['host']
   for addr in p.get('addresses',[]): ET.SubElement(x,f'{{{HNS}}}addr',{'ip':'v6' if ':' in addr else 'v4'}).text=addr
  elif op=='update_ds':
   c=ET.SubElement(cmd,f'{{{EPP}}}update'); x=ET.SubElement(c,f'{{{DNS}}}update'); ET.SubElement(x,f'{{{DNS}}}name').text=d; ext=ET.SubElement(cmd,f'{{{EPP}}}extension'); su=ET.SubElement(ext,f'{{{SNS}}}update'); add=ET.SubElement(su,f'{{{SNS}}}add')
   for rec in p.get('ds',[]):
    ds=ET.SubElement(add,f'{{{SNS}}}dsData'); ET.SubElement(ds,f'{{{SNS}}}keyTag').text=str(rec['key_tag']); ET.SubElement(ds,f'{{{SNS}}}alg').text=str(rec['algorithm']); ET.SubElement(ds,f'{{{SNS}}}digestType').text=str(rec['digest_type']); ET.SubElement(ds,f'{{{SNS}}}digest').text=rec['digest']
  else: raise ValueError('EPP_OPERATION_NOT_IMPLEMENTED')
  ET.SubElement(cmd,f'{{{EPP}}}clTRID').text='KEDDEH-'+qid
  return ET.tostring(root,encoding='unicode',xml_declaration=True)
 def rdap_domain(self,name,public=True):
  d=self.get_domain(name)
  if not d:return None
  events=[]
  if d['registry_created_at']:events.append({'eventAction':'registration','eventDate':d['registry_created_at']})
  if d['registry_expires_at']:events.append({'eventAction':'expiration','eventDate':d['registry_expires_at']})
  events.append({'eventAction':'last changed','eventDate':d['updated_at']})
  entities=[]
  if public:entities=[{'objectClassName':'entity','handle':'KEDDEH-REDACTED','roles':['registrant'],'remarks':[{'title':'Registration data exposure','description':['Public output is redacted by registrar policy; this is not evidence of a third-party privacy add-on.']}]}]
  return {'rdapConformance':['rdap_level_0'],'objectClassName':'domain','handle':d['registry_object_id'] or d['name'].upper(),'ldhName':d['name'],'status':(['client transfer prohibited'] if d['locked'] else []),'nameservers':[{'objectClassName':'nameserver','ldhName':x['host']} for x in d['nameservers']], 'secureDNS':{'delegationSigned':bool(d['ds']),'dsData':[{'keyTag':x['key_tag'],'algorithm':x['algorithm'],'digestType':x['digest_type'],'digest':x['digest']} for x in d['ds']]},'entities':entities,'events':events,'remarks':[{'title':'KEX evidence boundary','description':[f'Local state: {d["local_state"]}. Registry state: {d["registry_state"]}. Registry sponsorship is externally true only after registry readback.']} ]}
 def whois(self,name):
  d=self.get_domain(name)
  if not d:return 'No match for domain.\r\n'
  ns='\r\n'.join('Name Server: '+x['host'].upper() for x in d['nameservers'])
  created=d['registry_created_at'] or 'UNOBSERVED'; exp=d['registry_expires_at'] or 'UNOBSERVED'; sponsor=d['sponsor_registrar'] or 'UNOBSERVED'
  return f'Domain Name: {d["name"].upper()}\r\nRegistrar Software: KEDDEH REGISTRAR\r\nRegistry Sponsor: {sponsor}\r\nRegistry State: {d["registry_state"]}\r\nCreation Date: {created}\r\nExpiration Date: {exp}\r\nStatus: {"clientTransferProhibited" if d["locked"] else "ok"}\r\n{ns}\r\nRegistrant: REDACTED\r\n'
 def escrow_export(self):
  payload={'schema':'keddeh.registrar.escrow.v2','generated_at':now(),'territory':TERRITORY,'domains':[self.get_domain(d['name']) for d in self.list_domains()],'contacts':[dict(r) for r in self.db.execute('SELECT * FROM contacts ORDER BY id')],'hosts':[dict(r) for r in self.db.execute('SELECT * FROM hosts ORDER BY name')],'agreements':self.agreements(),'audit_head':self.audit_head()}
  body=canon(payload).encode(); return {'payload':payload,'sha256':sha_bytes(body),'bytes':len(body)}
 def audit_head(self):
  r=self.db.execute('SELECT seq,entry_hash,created_at FROM audit ORDER BY seq DESC LIMIT 1').fetchone(); return dict(r) if r else None
 def verify_audit(self):
  prev=None
  for r in self.db.execute('SELECT * FROM audit ORDER BY seq'):
   core={'event':r['event'],'subject':r['subject'],'payload':_json(r['payload_json']),'previous_hash':r['previous_hash'],'created_at':r['created_at']}
   if r['previous_hash']!=prev or sha_obj(core)!=r['entry_hash']: return False
   prev=r['entry_hash']
  return True
 def deployment_gate(self,domain):
  d=self._must_domain(fqdn(domain)); profile=registry_profile(d['name']); agreements=self.agreements(); bound=[a for a in agreements if a['state']=='BOUND']
  need=[]
  if profile['family']=='GTLD':
   if not any(a['kind']=='ICANN_RAA' and a['state']=='BOUND' for a in agreements):need.append('ICANN_RAA')
   if not any(a['scope']==tld_key(d['name']) and a['kind'].startswith('REGISTRY_RRA_') and a['state']=='BOUND' for a in agreements):need.append('REGISTRY_RRA_'+tld_key(d['name']).upper())
   if not any(a['kind']=='REGISTRAR_DATA_ESCROW' and a['state']=='BOUND' for a in agreements):need.append('REGISTRAR_DATA_ESCROW')
  else:
   if not any(a['kind']=='AUDA_REGISTRAR_AGREEMENT' and a['state']=='BOUND' for a in agreements):need.append('AUDA_REGISTRAR_AGREEMENT')
   if not any(a['kind']=='AU_REGISTRY_RRA' and a['state']=='BOUND' for a in agreements):need.append('AU_REGISTRY_RRA')
  return {'domain':d['name'],'registry_profile':profile,'authority_ready':not need,'missing_authorities':need,'registry_state':d['registry_state'],'delegation_ready_local':len(d['nameservers'])>=2,'ds_configured':bool(d['ds'])}
 def status(self):
  terr=json.loads(self.db.execute("SELECT v FROM meta WHERE k='territory'").fetchone()['v']); return {'service':'KEDDEH_REGISTRAR_V2','identity':'registrar://keddeh/sovereign/v2','territory':terr,'domains':len(self.list_domains()),'registry_queue':len(self.queue_list()),'audit_valid':self.verify_audit(),'registry_profiles':REGISTRY_PROFILES,'agreements':self.agreements()}
 def _must_domain(self,n):
  d=self.get_domain(n)
  if not d:raise KeyError('DOMAIN_NOT_FOUND')
  return d
