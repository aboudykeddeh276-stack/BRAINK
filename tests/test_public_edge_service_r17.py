from pathlib import Path
import subprocess,time,json,urllib.request,urllib.error

BASE=Path('/mnt/data')
SVC=BASE/'braink_public_edge_service_r17.py'
M1=BASE/'BRAINK_MACHINE_001_R9.vdisk'
LOG=BASE/'BRAINK_R17_PUBLIC_EDGE.log'

def get(path):
    try:
        with urllib.request.urlopen('http://127.0.0.1:17941'+path,timeout=2) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read())

log=open(LOG,'w')
p=subprocess.Popen(['/usr/bin/python3',str(SVC),str(M1),'0.0.0.0','17941'],stdout=log,stderr=subprocess.STDOUT)
try:
    end=time.time()+5
    health=None
    while time.time()<end:
        try:
            health=get('/health')
            if health[0]==200: break
        except Exception:
            time.sleep(.1)
    assert health and health[0]==200
    systems=get('/systems')
    dns=get('/dns')
    domain=get('/domain?name=keddeh.com')
    cloud=get('/cloud/object?id=CLOUD-OBJ-001')
    missing=get('/domain?name=missing.example')
    checks={
        'listener_health_pass': health[0]==200 and health[2]['status']=='PASS',
        'service_identity_header': health[1].get('X-BRAINK-Service')=='BRAINK::PUBLIC_EDGE::R17',
        'public_edge_identity': health[2]['edge_lexical_id']=='LEX://SERVER/BRAINK/PUBLIC_EDGE',
        'systems_route_pass': systems[0]==200 and 'DOMAIN_ROOT' in systems[2]['services'] and 'CLOUD_ROOT' in systems[2]['services'],
        'dns_route_pass': dns[0]==200 and dns[2]['authority']=='INTERNAL_RESIDENT_NOT_PUBLIC_AUTHORITY',
        'domain_route_pass': domain[0]==200 and domain[2]['domain']=='keddeh.com',
        'domain_authority_not_overpromoted': domain[2]['public_dns_authority']=='NOT_BOUND' and domain[2]['public_tls_authority']=='NOT_BOUND' and domain[2]['registry_authority']=='NOT_BOUND',
        'cloud_route_pass': cloud[0]==200 and cloud[2]['object']['object_id']=='CLOUD-OBJ-001',
        'unknown_domain_404': missing[0]==404,
        'external_binding_explicit': health[2]['external_binding_state']=='UNBOUND_PUBLIC_AUTHORITY'
    }
    assert all(checks.values()), checks
finally:
    p.terminate()
    try:p.wait(timeout=3)
    except: p.kill()
    log.close()
