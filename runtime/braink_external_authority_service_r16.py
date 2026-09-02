from __future__ import annotations
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dataclasses import dataclass, asdict
import json, socket, ssl, urllib.request, hashlib, threading, time, os

DOMAIN = os.environ.get('BRAINK_EXTERNAL_DOMAIN', 'keddeh.com')
HOST = os.environ.get('BRAINK_EXTERNAL_HOST', '0.0.0.0')
PORT = int(os.environ.get('BRAINK_EXTERNAL_PORT', '17941'))
LEDGER = Path(os.environ.get('BRAINK_EXTERNAL_LEDGER', '/mnt/data/BRAINK_EXTERNAL_AUTHORITY_SERVICE_R16_LEDGER.jsonl'))
STATE = Path(os.environ.get('BRAINK_EXTERNAL_STATE', '/mnt/data/BRAINK_EXTERNAL_AUTHORITY_SERVICE_R16_STATE.json'))

IDENTITY = {
    'service_id':'BRAINK::SERVICE::EXTERNAL_AUTHORITY::R16',
    'lexical_id':'LEX://BRAINK/SERVICE/EXTERNAL_AUTHORITY',
    'vector_id':f'VEC://SERVICE/EXTERNAL_AUTHORITY/{HOST}:{PORT}',
    'domain_root':f'LEX://DOMAIN/{DOMAIN}',
    'dns_root':f'LEX://DNS/{DOMAIN}',
    'registrar_root':f'LEX://REGISTRAR/{DOMAIN}',
    'tls_root':f'LEX://TLS/{DOMAIN}',
    'vfs_role':'RESOLVER_ONLY'
}

@dataclass
class Probe:
    name:str
    state:str
    detail:str
    evidence:dict

lock=threading.Lock()
def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def dns_probe(domain):
    try:
        rows=socket.getaddrinfo(domain,443,type=socket.SOCK_STREAM)
        return Probe('PUBLIC_DNS_READBACK','PASS','System resolver returned addresses',{'addresses':sorted({r[4][0] for r in rows})})
    except Exception as e:
        return Probe('PUBLIC_DNS_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e)})

def https_probe(domain):
    try:
        req=urllib.request.Request('https://'+domain+'/',method='HEAD',headers={'User-Agent':'BRAINK-ExternalAuthority-R16/1.0'})
        with urllib.request.urlopen(req,timeout=7) as r:
            return Probe('PUBLIC_HTTPS_READBACK','PASS','HTTPS endpoint responded',{'status':r.status,'url':r.geturl()})
    except Exception as e:
        return Probe('PUBLIC_HTTPS_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e)})

def tls_probe(domain):
    try:
        ctx=ssl.create_default_context()
        with socket.create_connection((domain,443),timeout=5) as raw:
            with ctx.wrap_socket(raw,server_hostname=domain) as s:
                cert=s.getpeercert(binary_form=True); parsed=s.getpeercert()
        return Probe('PUBLIC_TLS_READBACK','PASS','TLS peer certificate observed',{'sha256':hashlib.sha256(cert).hexdigest(),'subject':parsed.get('subject'),'issuer':parsed.get('issuer'),'notAfter':parsed.get('notAfter')})
    except Exception as e:
        return Probe('PUBLIC_TLS_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e)})

def rdap_probe(domain):
    url=f'https://rdap.verisign.com/com/v1/domain/{domain}'
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'BRAINK-ExternalAuthority-R16/1.0','Accept':'application/rdap+json,application/json'})
        with urllib.request.urlopen(req,timeout=7) as r: body=json.loads(r.read().decode())
        return Probe('PUBLIC_RDAP_READBACK','PASS','Registry RDAP state observed',{'ldhName':body.get('ldhName'),'status':body.get('status'),'nameservers':[n.get('ldhName') for n in body.get('nameservers',[])]})
    except Exception as e:
        return Probe('PUBLIC_RDAP_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e),'url':url})

def observe():
    probes=[dns_probe(DOMAIN),https_probe(DOMAIN),tls_probe(DOMAIN),rdap_probe(DOMAIN)]
    receipt={
        'schema':'braink.external-authority-service.r16.observation','time':now(),'identity':IDENTITY,'domain':DOMAIN,
        'probes':[asdict(p) for p in probes],
        'promotion':{
            'public_dns':'PASS' if any(p.name=='PUBLIC_DNS_READBACK' and p.state=='PASS' for p in probes) else 'UNPROMOTED',
            'public_https':'PASS' if any(p.name=='PUBLIC_HTTPS_READBACK' and p.state=='PASS' for p in probes) else 'UNPROMOTED',
            'public_tls':'PASS' if any(p.name=='PUBLIC_TLS_READBACK' and p.state=='PASS' for p in probes) else 'UNPROMOTED',
            'public_rdap':'PASS' if any(p.name=='PUBLIC_RDAP_READBACK' and p.state=='PASS' for p in probes) else 'UNPROMOTED'},
        'mutation_authority':{'public_dns':'BLOCKED_NO_AUTHORITY_CREDENTIAL','registry_registrar':'BLOCKED_NO_EPP_OR_REGISTRAR_AUTHORITY','ca_tls_issuance':'BLOCKED_NO_CA_OR_ACME_AUTHORITY'},
        'status':'PUBLIC_READBACK_PARTIAL_OR_FULL' if any(p.state=='PASS' for p in probes) else 'BOUNDARY_CLASSIFIED_NO_PUBLIC_READBACK'}
    with lock:
        LEDGER.parent.mkdir(parents=True,exist_ok=True)
        with LEDGER.open('a') as f: f.write(json.dumps(receipt,sort_keys=True)+'\n')
        STATE.write_text(json.dumps(receipt,indent=2))
    return receipt

class H(BaseHTTPRequestHandler):
    def sendj(self,status,obj):
        raw=json.dumps(obj,sort_keys=True).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/health': return self.sendj(200,{'status':'PASS','identity':IDENTITY,'domain':DOMAIN,'ledger':str(LEDGER),'state_file':str(STATE)})
        if self.path=='/state':
            if not STATE.exists(): return self.sendj(404,{'status':'NO_OBSERVATION_YET'})
            return self.sendj(200,json.loads(STATE.read_text()))
        if self.path=='/observe': return self.sendj(200,observe())
        return self.sendj(404,{'status':'NOT_FOUND'})
    def do_POST(self):
        if self.path in {'/dns/update','/registrar/update','/tls/issue'}:
            return self.sendj(403,{'status':'BLOCKED','reason':'EXTERNAL_MUTATION_AUTHORITY_NOT_INSTALLED','service_id':IDENTITY['service_id']})
        return self.sendj(404,{'status':'NOT_FOUND'})
    def log_message(self,*args): pass

if __name__=='__main__':
    print(json.dumps({'status':'LISTENING','identity':IDENTITY,'domain':DOMAIN,'host':HOST,'port':PORT}),flush=True)
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
