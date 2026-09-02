from __future__ import annotations
from pathlib import Path
import json,hashlib
AUTHOR='AKD'; ROOT='enterprise/governance/AKD_AUTHORSHIP_ROOT.json'
def load_json(p):
    try:return json.loads(Path(p).read_text())
    except Exception:return None
def audit(repo_root='.'):
    root=Path(repo_root); ledger=load_json(root/'deployment/AUTHORSHIP_LEDGER_R2.json') or {'lineage':[]}
    bindings={x['deployment_path']:x for x in ledger.get('lineage',[])}; results=[]
    for p in sorted((root/'deployment').glob('KEDDEH_SYSTEMS_*.json')):
        if 'AUTHORSHIP' in p.name: continue
        rel=str(p.relative_to(root)); data=load_json(p)
        if not isinstance(data,dict):
            results.append({'path':rel,'classification':'ORPHANED_AKD_SERVICE','reason':'UNREADABLE_OR_NON_OBJECT'}); continue
        direct=data.get('author_id')==AUTHOR and data.get('authorship_root')==ROOT
        side=bindings.get(rel); inherited=bool(side and side.get('classification') in ('AKD_AUTHORED','AKD_AUTHORED_INHERITED'))
        if direct: c='AKD_AUTHORED'; reason='DIRECT'
        elif inherited: c=side['classification']; reason='LEDGER_BINDING'
        else: c='ORPHANED_AKD_SERVICE'; reason='NO_VALID_AKD_LINEAGE'
        results.append({'path':rel,'classification':c,'reason':reason,'service_id':side.get('service_id') if side else data.get('service_id') or data.get('release')})
    summary={'total':len(results),'akd_authored':sum(r['classification']=='AKD_AUTHORED' for r in results),'akd_inherited':sum(r['classification']=='AKD_AUTHORED_INHERITED' for r in results),'orphaned':sum(r['classification']=='ORPHANED_AKD_SERVICE' for r in results)}
    packet={'schema':'keddeh.systems.authorship-audit.r26/v1','summary':summary,'results':results}; packet['audit_root']=hashlib.sha256(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()).hexdigest(); return packet
if __name__=='__main__':
    import sys; r=audit(sys.argv[1] if len(sys.argv)>1 else '.'); print(json.dumps(r,indent=2)); raise SystemExit(2 if r['summary']['orphaned'] else 0)
