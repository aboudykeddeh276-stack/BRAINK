import json,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from enterprise.adapters.payment_rail import UNBOUND
from enterprise.adapters.connector_bindings import MAIL,IDENTITY,CALENDAR,DRIVE
from enterprise.runtime.process_supervisor import ManagedProcess
checks={}
reg=json.loads((ROOT/'enterprise/adapters/BINDING_REGISTER_R18.json').read_text())
checks['payment_not_falsely_bound']=not UNBOUND.qualified() and reg['bindings']['payments']['state']=='ADAPTER_IMPLEMENTED_UNBOUND'
checks['mail_connector_bound']=MAIL.state=='BOUND_CONTROL_PLANE' and 'send' in MAIL.operations
checks['identity_read_bound']=IDENTITY.state=='BOUND_READ_ONLY'
checks['drive_write_bound']=DRIVE.state=='BOUND_AND_TESTED'
checks['calendar_boundary_explicit']=CALENDAR.state=='BOUND_READ_ONLY'
p=ManagedProcess('ingress',[sys.executable,str(ROOT/'enterprise/runtime/http_ingress.py')]);p.start();time.sleep(.5)
checks['process_alive']=p.alive()
with urllib.request.urlopen('http://127.0.0.1:19420/health',timeout=3) as r:checks['http_health']=json.loads(r.read())['status']=='OK'
with urllib.request.urlopen('http://127.0.0.1:19420/metrics',timeout=3) as r:metrics=r.read().decode()
checks['metrics_exposed']='braink_runtime_requests_total' in metrics and 'braink_runtime_uptime_seconds' in metrics
p.stop();checks['process_stopped']=not p.alive()
print(json.dumps({'checks':checks},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
