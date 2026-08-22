from pathlib import Path
import subprocess,time,json,urllib.request,urllib.parse,urllib.error,os

BASE=Path('/mnt/data')
SVC=BASE/'braink_typed_service_fabric_r13.py'
M1=BASE/'BRAINK_MACHINE_001_R9.vdisk'
M2=BASE/'BRAINK_MACHINE_002_R9.vdisk'
BLOCK=4096; MUTATION_OFF=1024*BLOCK

def wait_health(port,timeout=5):
    end=time.time()+timeout
    while time.time()<end:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.5) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(.1)
    raise RuntimeError('E_HEALTH_TIMEOUT')

def get(port,path):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=2) as r:
        return r.status,json.loads(r.read())

def post(port,path,obj):
    req=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=2) as r:
            return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read())

def copy_mutation_state(src,dst):
    with open(src,'rb') as f:
        f.seek(MUTATION_OFF); buf=f.read(BLOCK)
    with open(dst,'r+b') as f:
        f.seek(MUTATION_OFF); f.write(buf); f.flush(); os.fsync(f.fileno())

def run():
    l1=open(BASE/'BRAINK_R13_M1.log','w'); l2=open(BASE/'BRAINK_R13_M2.log','w')
    p1=subprocess.Popen(['python',str(SVC),str(M1),'0.0.0.0','17931'],stdout=l1,stderr=subprocess.STDOUT)
    p2=subprocess.Popen(['python',str(SVC),str(M2),'0.0.0.0','17932'],stdout=l2,stderr=subprocess.STDOUT)
    p1r=None
    try:
        wait_health(17931); wait_health(17932)
        roots={}
        for lex in ['LEX://SERVER/GLOBAL','LEX://DOMAIN/keddeh.com','LEX://DNS/keddeh.com','LEX://REGISTRAR/keddeh.com','LEX://TLS/keddeh.com','LEX://CLOUD/BRAINK/GLOBAL']:
            st,d=get(17931,'/resolve?lexical_id='+urllib.parse.quote(lex,safe='')); roots[lex]=(st==200 and d['status']=='PASS')
        cloud=post(17931,'/cloud/write',{'object_id':'CLOUD-OBJ-001','payload':'BRAINK cloud payload R13'})
        dns=post(17931,'/dns/update',{'authority':'INTERNAL','name':'app.keddeh.com','value':'LEX://SERVER/GLOBAL'})
        reg=post(17931,'/registrar/update',{'authority':'INTERNAL','lock':True})
        tls=post(17931,'/tls/update',{'authority':'INTERNAL','mode':'PENDING_EXTERNAL_CA'})
        dns_ext=post(17931,'/dns/update',{'authority':'PUBLIC','name':'app.keddeh.com','value':'203.0.113.1'})
        reg_ext=post(17931,'/registrar/update',{'authority':'REGISTRY','lock':False})
        tls_ext=post(17931,'/tls/update',{'authority':'CA','mode':'ISSUED'})
        copy_mutation_state(M1,M2)
        _,m1cloud=get(17931,'/cloud/read?object_id=CLOUD-OBJ-001'); _,m2cloud=get(17932,'/cloud/read?object_id=CLOUD-OBJ-001')
        _,m2dns=get(17932,'/dns/read'); _,m2reg=get(17932,'/registrar/read'); _,m2tls=get(17932,'/tls/read')
        p1.terminate(); p1.wait(timeout=3)
        _,failcloud=get(17932,'/cloud/read?object_id=CLOUD-OBJ-001'); _,faildomain=get(17932,'/resolve?lexical_id='+urllib.parse.quote('LEX://DOMAIN/keddeh.com',safe=''))
        copy_mutation_state(M2,M1)
        l1.close(); l1=open(BASE/'BRAINK_R13_M1.log','a')
        p1r=subprocess.Popen(['python',str(SVC),str(M1),'0.0.0.0','17931'],stdout=l1,stderr=subprocess.STDOUT)
        h1=wait_health(17931); _,reconcloud=get(17931,'/cloud/read?object_id=CLOUD-OBJ-001')
        checks={'all_six_roots_resolve':all(roots.values()),'cloud_write_pass':cloud[0]==200,'dns_internal_pass':dns[0]==200,'registrar_internal_pass':reg[0]==200,'tls_internal_pass':tls[0]==200,'public_dns_blocked':dns_ext[0]==403,'registry_mutation_blocked':reg_ext[0]==403,'ca_mutation_blocked':tls_ext[0]==403,'replicated_cloud_hash_equal':m1cloud['object']['payload_sha256']==m2cloud['object']['payload_sha256'],'secondary_dns_state_present':'app.keddeh.com' in m2dns['records'],'secondary_registrar_state_present':'keddeh.com' in m2reg['registrar_state'],'secondary_tls_state_present':'keddeh.com' in m2tls['tls_state'],'secondary_cloud_available_after_primary_loss':failcloud['status']=='PASS','secondary_domain_resolution_after_primary_loss':faildomain['status']=='PASS','primary_restart_pass':h1['status']=='PASS','reconciled_cloud_hash_equal':reconcloud['object']['payload_sha256']==m2cloud['object']['payload_sha256']}
        assert all(checks.values()), checks
        return checks
    finally:
        for p in (p1,p2,p1r):
            if p and p.poll() is None:
                p.terminate()
                try:p.wait(timeout=2)
                except: p.kill()
        try:l1.close()
        except:pass
        try:l2.close()
        except:pass

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
