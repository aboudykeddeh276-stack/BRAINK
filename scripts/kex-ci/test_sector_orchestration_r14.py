import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.sector_runtime import SectorRuntime
from enterprise.sector_agent_fabric import SectorAgentFabric,GROUPS
from enterprise.sector_selector import rank_sectors

registry=json.loads((ROOT/'enterprise/SECTOR_FUNCTION_REGISTER_R14.json').read_text())
rt=SectorRuntime(registry)
fabric=SectorAgentFabric(rt)
checks={}
checks['twelve_sectors']=len(registry['sectors'])==12
checks['all_have_functions']=all(len(v['market_functions'])>=9 for v in registry['sectors'].values())
for sector in ['AI_CLOUD_INFRA','CYBERSECURITY','ENTERPRISE_AUTOMATION']:
    d=fabric.deploy_sector(sector)
    expected=len(d['modules'])*len(GROUPS)*2
    checks[f'{sector}_edge_count']=len(d['edges'])==expected
    first=d['modules'][0]
    wm=[e for e in d['edges'] if e.work_module_id==first.module_id]
    checks[f'{sector}_recursive_fold']=len(wm)==10
    for e in wm:
        rt.complete(e,'PASS',{'sector':sector,'module':first.module_id,'scope':e.scope})
ranked=rank_sectors(registry)
checks['priority_sectors_rank_first']=all(registry['sectors'][x['sector']]['priority']==1 for x in ranked[:4])
checks['collapse_receipts']=bool(rt.collapse_subtree('supervisor://sector/ai_cloud_infra')['receipt_root'])
print(json.dumps({'checks':checks,'ranked':ranked[:6],'edge_count':len(rt.edges),'receipt_count':len(rt.receipts)},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
