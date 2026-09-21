#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

DOMAIN="casepath.com.au"
CANONICAL="app://casepath"
REQUIRED={"index.html":True,"glossary.html":True,"privacy.html":True,"terms.html":True}
ALLOWED={
 "CP-PUB-001":{"id":"action://casepath/origin/discover"},
 "CP-PUB-002":{"id":"action://casepath/publish/apply"},
 "CP-PUB-003":{"id":"action://casepath/public/readback"},
}
ACTUATOR_NAMES={
 "casepath_production_actuator_v50.py":True,
 "casepath_production_actuator.py":True,
 "KEX-SEED-CASEPATH-PROD-ACTUATOR-20260826T233107Z-5804B67605__casepath_production_actuator.py":True,
}
def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def root_state(root:Path)->dict:
 root=root.expanduser().resolve(); files={}
 for name in REQUIRED:
  p=root/name; files[name]={"id":name,"exists":p.is_file(),"bytes":p.stat().st_size if p.is_file() else None,"sha256":sha(p.read_bytes()) if p.is_file() else None}
 idx=root/'index.html'; marker=idx.is_file() and 'casepath' in idx.read_text(errors='replace').lower()
 return {"schema":"casepath.origin-shape.v50","root":str(root),"required":files,"casepath_marker":marker,"pass":all(x['exists'] for x in files.values()) and marker}
def candidate_roots()->dict[str,Path]:
 out={}; explicit=os.environ.get('CASEPATH_DOCROOT')
 if explicit:out['candidate://env/CASEPATH_DOCROOT']=Path(explicit)
 home=Path.home()
 for cid,p in {"candidate://home/CASEPATH":home/'CASEPATH',"candidate://home/casepath":home/'casepath',"candidate://web_root":Path('/web_root'),"candidate://var/www/casepath":Path('/var/www/casepath')}.items():out[cid]=p
 scan={"scan://home":home,"scan://users-ak":Path('/Users/ak')}; seen={str(p.expanduser()) for p in out.values()}
 for sid,base in scan.items():
  if not base.exists():continue
  depth0=len(base.resolve().parts)
  for dirpath,dirnames,filenames in os.walk(base):
   p=Path(dirpath); depth=len(p.resolve().parts)-depth0
   if depth>6:dirnames[:]=[];continue
   dirnames[:]=[d for d in dirnames if d not in {'.git','node_modules','Library','.Trash','.cache','Applications','System','Volumes'}]
   if set(REQUIRED).issubset(set(filenames)) and str(p) not in seen:out[f'{sid}/shape/{sha(str(p).encode())[:12]}']=p;seen.add(str(p))
 return out
def discover_origin()->dict:
 obs={}; winners={}
 for cid,path in candidate_roots().items():
  try:state=root_state(path)
  except Exception as e:state={"schema":"casepath.origin-shape.v50","root":str(path),"pass":False,"error":type(e).__name__+':'+str(e)}
  obs[cid]={"id":cid,"state":state}
  if state.get('pass'):winners[cid]={"id":cid,"root":state['root'],"state":state}
 if len(winners)==1:return {"schema":"casepath.origin-discovery.v50","action":"CP-PUB-001","state":"PASS_UNIQUE_VERIFIED_ORIGIN","canonical":CANONICAL,"binding":{"origin://casepath/current":next(iter(winners.values()))},"observations":obs}
 if len(winners)>1:return {"schema":"casepath.origin-discovery.v50","action":"CP-PUB-001","state":"FAIL_CLOSED_MULTIPLE_VALID_ORIGINS","canonical":CANONICAL,"winners":winners,"observations":obs}
 return {"schema":"casepath.origin-discovery.v50","action":"CP-PUB-001","state":"FAIL_CLOSED_NO_VERIFIED_ORIGIN","canonical":CANONICAL,"observations":obs}
def resolve_actuator()->Path:
 out={}; explicit=os.environ.get('CASEPATH_PRODUCTION_ACTUATOR')
 if explicit:out['actuator://env']=Path(explicit)
 for base in {"home":Path.home(),"gdrive":Path.home()/'Google Drive',"mydrive":Path.home()/'My Drive',"users-ak":Path('/Users/ak')}.values():
  if not base.exists():continue
  for name in ACTUATOR_NAMES:
   direct=base/name
   if direct.is_file():out[f'actuator://{sha(str(direct).encode())[:12]}']=direct
 valid={k:p.resolve() for k,p in out.items() if p.is_file()}
 if len(valid)==1:return next(iter(valid.values()))
 if not valid:raise RuntimeError('CASEPATH_PRODUCTION_ACTUATOR_LOCAL_COPY_UNRESOLVED')
 raise RuntimeError('MULTIPLE_CASEPATH_PRODUCTION_ACTUATORS_REQUIRE_EXPLICIT_BINDING')
def publish(origin:Path,apply:bool)->dict:
 state=root_state(origin)
 if not state['pass']:return {"schema":"casepath.publish-dispatch.v50","action":"CP-PUB-002","state":"FAIL_CLOSED_ORIGIN_SHAPE","origin":state}
 try:actuator=resolve_actuator()
 except Exception as exc:return {"schema":"casepath.publish-dispatch.v50","action":"CP-PUB-002","state":"FAIL_CLOSED_ACTUATOR_UNBOUND","error":type(exc).__name__+':'+str(exc),"origin":state}
 if not apply:return {"schema":"casepath.publish-dispatch.v50","action":"CP-PUB-002","state":"READY_NOT_APPLIED","origin":state,"actuator":str(actuator)}
 env=os.environ.copy();env['CASEPATH_DOCROOT']=str(origin.resolve())
 run=subprocess.run([sys.executable,str(actuator),'deploy','--docroot',str(origin.resolve())],capture_output=True,text=True,env=env)
 try:payload=json.loads(run.stdout)
 except Exception:payload={"raw_stdout":run.stdout[-8000:]}
 return {"schema":"casepath.publish-dispatch.v50","action":"CP-PUB-002","state":"EXECUTED" if run.returncode==0 else "FAILED","returncode":run.returncode,"origin":root_state(origin),"actuator":str(actuator),"actuator_receipt":payload,"stderr":run.stderr[-4000:]}
def readback(expected_marker:str|None)->dict:
 try:
  req=urllib.request.Request(f'https://{DOMAIN}/',headers={'User-Agent':'KEX-CasePath-Bridge-v50/2026.08'})
  with urllib.request.urlopen(req,timeout=20) as r:body=r.read();status=r.status
  text=body.decode('utf-8',errors='replace')
  return {"schema":"casepath.public-readback.v50","action":"CP-PUB-003","state":"OBSERVED","status":status,"body_sha256":sha(body),"casepath":'casepath' in text.lower(),"expected_marker":expected_marker,"marker_match":expected_marker in text if expected_marker else None}
 except Exception as exc:return {"schema":"casepath.public-readback.v50","action":"CP-PUB-003","state":"UNAVAILABLE","error":type(exc).__name__+':'+str(exc)}
def handle(patch_id:str,apply=False,origin=None,expected_marker=None)->dict:
 if patch_id not in ALLOWED:return {"state":"FAIL_CLOSED_ACTION_NOT_ALLOWLISTED","patch_id":patch_id}
 if patch_id=='CP-PUB-001':return discover_origin()
 if patch_id=='CP-PUB-002':
  value=origin or os.environ.get('CASEPATH_DOCROOT')
  return publish(Path(value),apply) if value else {"state":"FAIL_CLOSED_DOCROOT_UNBOUND","patch_id":patch_id}
 return readback(expected_marker)
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('patch_id',choices=sorted(ALLOWED));ap.add_argument('--origin');ap.add_argument('--apply',action='store_true');ap.add_argument('--expected-marker');ap.add_argument('--receipt-dir',default='.')
 ns=ap.parse_args();result=handle(ns.patch_id,ns.apply,ns.origin,ns.expected_marker);Path(ns.receipt_dir).mkdir(parents=True,exist_ok=True);out=Path(ns.receipt_dir)/f'{ns.patch_id}_{time.strftime("%Y%m%dT%H%M%S")}.json';out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));print(f'RECEIPT={out}',file=sys.stderr)
 return 0 if result.get('state') in {'PASS_UNIQUE_VERIFIED_ORIGIN','READY_NOT_APPLIED','EXECUTED','OBSERVED'} else 2
if __name__=='__main__':raise SystemExit(main())
