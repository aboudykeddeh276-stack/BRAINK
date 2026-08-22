from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, socket, ssl, urllib.request, hashlib

DOMAIN='keddeh.com'
OUT=Path('/mnt/data/BRAINK_R14_EXTERNAL_AUTHORITY_RECEIPT.json')

@dataclass
class Probe:
    name:str
    state:str
    detail:str
    evidence:dict

def dns_probe(domain:str)->Probe:
    try:
        rows=socket.getaddrinfo(domain,443,type=socket.SOCK_STREAM)
        addrs=sorted({r[4][0] for r in rows})
        return Probe('PUBLIC_DNS_READBACK','PASS','System resolver returned addresses',{'addresses':addrs})
    except Exception as e:
        return Probe('PUBLIC_DNS_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e)})

def tls_probe(domain:str)->Probe:
    try:
        ctx=ssl.create_default_context()
        with socket.create_connection((domain,443),timeout=5) as raw:
            with ctx.wrap_socket(raw,server_hostname=domain) as s:
                cert=s.getpeercert(binary_form=True); parsed=s.getpeercert()
        return Probe('PUBLIC_TLS_READBACK','PASS','TLS peer certificate observed',{'sha256':hashlib.sha256(cert).hexdigest(),'subject':parsed.get('subject'),'issuer':parsed.get('issuer'),'notAfter':parsed.get('notAfter')})
    except Exception as e:
        return Probe('PUBLIC_TLS_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e)})

def http_probe(domain:str)->Probe:
    try:
        req=urllib.request.Request('https://'+domain+'/',method='HEAD',headers={'User-Agent':'BRAINK-R14/1.0'})
        with urllib.request.urlopen(req,timeout=7) as r:
            return Probe('PUBLIC_HTTPS_READBACK','PASS','HTTPS endpoint responded',{'status':r.status,'url':r.geturl(),'headers':dict(r.headers)})
    except Exception as e:
        return Probe('PUBLIC_HTTPS_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e)})

def rdap_probe(domain:str)->Probe:
    url=f'https://rdap.verisign.com/com/v1/domain/{domain}'
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'BRAINK-R14/1.0','Accept':'application/rdap+json,application/json'})
        with urllib.request.urlopen(req,timeout=7) as r:
            body=json.loads(r.read().decode())
        return Probe('PUBLIC_RDAP_READBACK','PASS','Registry RDAP state observed',{'ldhName':body.get('ldhName'),'status':body.get('status'),'nameservers':[n.get('ldhName') for n in body.get('nameservers',[])],'entities':[e.get('handle') for e in body.get('entities',[])],'events':body.get('events',[])})
    except Exception as e:
        return Probe('PUBLIC_RDAP_READBACK','UNREACHABLE_FROM_EXECUTION_ENVIRONMENT',type(e).__name__,{'error':str(e),'url':url})

probes=[dns_probe(DOMAIN),http_probe(DOMAIN),tls_probe(DOMAIN),rdap_probe(DOMAIN)]
receipt={'schema':'braink.external-authority-adapter.r14.receipt','domain':DOMAIN,'internal_bindings':{'domain':'LEX://DOMAIN/keddeh.com','dns':'LEX://DNS/keddeh.com','registrar':'LEX://REGISTRAR/keddeh.com','tls':'LEX://TLS/keddeh.com','server':'LEX://SERVER/GLOBAL','cloud':'LEX://CLOUD/BRAINK/GLOBAL'},'probes':[asdict(p) for p in probes],'mutation_authority':{'public_dns':'BLOCKED_NO_AUTHORITY_CREDENTIAL','registry_registrar':'BLOCKED_NO_EPP_OR_REGISTRAR_AUTHORITY','ca_tls_issuance':'BLOCKED_NO_CA_OR_ACME_AUTHORITY'},'execution_boundary':'This runtime cannot currently resolve public hosts; no WAN/public-authority completion claim is permitted.','status':'PASS_BOUNDARY_ENFORCED' if all(p.state!='PASS' for p in probes) else 'PARTIAL_PUBLIC_READBACK'}
OUT.write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
