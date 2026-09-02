import json,sys,tempfile,sqlite3,subprocess,os,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from enterprise.foundry.foundry_os import FoundryOS
with tempfile.TemporaryDirectory() as td:
 f=FoundryOS(ROOT/'enterprise/foundry/MASTER_DATASET_R1.json',Path(td)/'estate'); built=f.build_all('KEDDEH_SYSTEMS'); master=f.master; checks={}
 checks['nine_foundries']=len(built)==9
 checks['all_120_functions_preserved']=sum(len(v['functions']) for v in master['sector_products']['products'].values())==120
 checks['all_12_sectors_preserved']=len(master['sector_products']['products'])==12
 sm=json.loads((Path(td)/'estate/business_enterprise_structure/service_matrix.json').read_text()); checks['business_has_120']=len(sm['services'])==120
 work=json.loads((Path(td)/'estate/agentics/work_module_register.json').read_text()); checks['agentics_has_120_work_modules']=len(work['work_modules'])==120
 routes=json.loads((Path(td)/'estate/landing_page/domain_routes.json').read_text()); checks['landing_has_120_routes']=len(routes['routes'])==120
 checks['workspace_db']=sqlite3.connect(Path(td)/'estate/workspace/workspace.sqlite3').execute('select count(*) from workspaces').fetchone()[0]==1
 checks['filesystem_db']=sqlite3.connect(Path(td)/'estate/file_system/vfs.sqlite3').execute("select count(*) from sqlite_master where type='table'").fetchone()[0]>=2
 checks['customer_db']=sqlite3.connect(Path(td)/'estate/customer_file_base/customer_files.sqlite3').execute("select count(*) from sqlite_master where type='table'").fetchone()[0]>=5
 checks['research_db']=sqlite3.connect(Path(td)/'estate/publishing_process_research/research_publish.sqlite3').execute("select count(*) from sqlite_master where type='table'").fetchone()[0]>=4
 srv=Path(td)/'estate/server'; env=os.environ.copy(); env['PORT']='18991'; proc=subprocess.Popen([sys.executable,str(srv/'server_runtime.py')],cwd=srv,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  time.sleep(.5); health=json.loads(urllib.request.urlopen('http://127.0.0.1:18991/health',timeout=2).read()); services=json.loads(urllib.request.urlopen('http://127.0.0.1:18991/services',timeout=2).read()); checks['server_health']=health['status']=='ok'; checks['server_exposes_120']=len(services['services'])==120
 finally:
  proc.terminate(); proc.wait(timeout=3)
 checks['same_master_root_all']=len({v['master_dataset']['root'] for v in built.values()})==1
 print(json.dumps({'checks':checks,'foundries':list(built),'master_root':f.master_root},indent=2)); raise SystemExit(0 if all(checks.values()) else 2)
