import sys,json,time,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from enterprise.market.service_fabric_r24 import MarketServiceFabric

db=ROOT/'runtime/test_r24.sqlite3'
if db.exists(): db.unlink()
s=MarketServiceFabric(db)
c=s.create_customer('CasePath Customer','customer@example.invalid')
w=s.create_workspace(c['customer_id'],'Legal Matter')
a1=s.write_artifact(w['workspace_id'],'evidence/statement.txt','first')
a2=s.write_artifact(w['workspace_id'],'evidence/statement.txt','second')
site=s.create_site(c['customer_id'],'CasePath Landing','casepath.example.invalid','LANDING_PAGE')
s.put_page(site['site_id'],'/','CasePath','<h1>CasePath</h1>')
pub=s.publish_site(site['site_id'])
role=s.register_role('Research Supervisor','research:*',True)
agent=s.register_agent('Research Agent',role['role_id'])
wm=s.create_work_module('research_mastery','research_packet','Research current matter')
asn=s.assign_agent(wm['work_module_id'],agent['agent_id'],'supervisor://research','research','research:casepath')
dep=s.deploy_server_set('casepath','agentic_ai',2,{'region':'AU-SA','source':'R24'})
m=s.metrics()
checks={
 'customer_workspace':m['customers']==1 and m['workspaces']==1,
 'revisioned_artifacts':a1['revision']==1 and a2['revision']==2 and a1['sha256']!=a2['sha256'],
 'landing_published':pub['state']=='QUALIFIED_LOCAL',
 'hr_agent_assignment':m['roles']==1 and m['agents']==1 and m['assignments']==1,
 'server_configured':dep['state']=='CONFIGURED_LOCAL',
 'receipts_generated':m['receipts']>=10
}
p=subprocess.Popen([sys.executable,'-m','enterprise.market.http_api_r24'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    time.sleep(.7)
    with urllib.request.urlopen('http://127.0.0.1:19620/health',timeout=3) as r: health=json.loads(r.read())
    with urllib.request.urlopen('http://127.0.0.1:19620/metrics',timeout=3) as r: metrics=json.loads(r.read())
    checks['http_health']=health['status']=='OK'
    checks['http_metrics']='state_root' in metrics
finally:
    p.terminate(); p.wait(timeout=3)
print(json.dumps({'checks':checks,'metrics':m},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
