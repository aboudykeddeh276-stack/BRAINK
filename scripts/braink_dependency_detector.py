#!/usr/bin/env python3
from __future__ import annotations
import ast, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT=Path(os.environ.get('GITHUB_WORKSPACE','.') ).resolve()
POLICY=ROOT/'.braink/dependency-edges.json'
OUT_GRAPH=ROOT/'reports/BRAINK_DEPENDENCY_GRAPH.json'
OUT_SNAPSHOT=ROOT/'reports/BRAINK_DEPENDENCY_SNAPSHOT.json'

SCAN_DIRS=('enterprise','runtime','modules','kex','scripts')

def purl_generic(name, version='local'):
    return f"pkg:generic/{quote(name, safe='')}@{quote(version, safe='')}"

def module_name(path:Path):
    rel=path.relative_to(ROOT).with_suffix('')
    return '.'.join(rel.parts)

def git_sha(path:Path):
    try:
        return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    except Exception:
        return 'unknown'

def scan_python():
    files=[]
    for d in SCAN_DIRS:
        p=ROOT/d
        if p.exists(): files += list(p.rglob('*.py'))
    by_mod={module_name(p):p for p in files}
    edges=[]
    for src in files:
        try: tree=ast.parse(src.read_text(encoding='utf-8'))
        except Exception: continue
        imports=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): imports += [a.name for a in n.names]
            elif isinstance(n,ast.ImportFrom) and n.module: imports.append(n.module)
        for imp in imports:
            candidates=[m for m in by_mod if m==imp or m.endswith('.'+imp) or imp.startswith(m+'.')]
            for dstm in candidates:
                dst=by_mod[dstm]
                if dst!=src:
                    edges.append({'source':str(src.relative_to(ROOT)),'target':str(dst.relative_to(ROOT)),'class':'MODULE_DEPENDENCY','relationship':'direct','scope':'runtime','observed':True})
    return edges

def load_policy():
    return json.loads(POLICY.read_text())

def main():
    policy=load_policy(); edges=scan_python(); cuts=[]; required_fail=[]
    repo_nodes=[]
    for e in policy.get('required_repository_edges',[]):
        checkout=ROOT/e.get('checkout_path','') if e.get('checkout_path') else None
        present=bool(checkout and checkout.exists())
        sha=git_sha(checkout) if present else 'missing'
        edge=dict(e); edge['observed']=present; edge['resolved_sha']=sha
        if e.get('required_paths') and present:
            missing=[p for p in e['required_paths'] if not (checkout/p).exists()]
            edge['missing_required_paths']=missing
            present=present and not missing; edge['observed']=present
        edges.append(edge)
        repo_nodes.append({'repository':e['target'],'checkout_path':e.get('checkout_path'),'sha':sha,'observed':edge['observed']})
        if not edge['observed']: required_fail.append(edge)
    for e in policy.get('expected_module_edges',[]):
        src=ROOT/e['source']; target=e['target']
        target_exists = target.startswith('repository://') or (ROOT/target).exists()
        observed=src.exists() and target_exists
        edge=dict(e); edge['observed']=observed
        if not observed:
            edge['classification']='MISSING_INTEGRATION_GRAPH_CUT'; cuts.append(edge)
        edges.append(edge)
    sha=os.environ.get('GITHUB_SHA') or git_sha(ROOT)
    ref=os.environ.get('GITHUB_REF','refs/heads/local')
    graph={'schema':'braink.dependency-graph.v1','commit_sha':sha,'ref':ref,'edge_classes':policy['edge_classes'],'nodes':repo_nodes,'edges':edges,'graph_cuts':cuts,'required_failures':required_fail}
    OUT_GRAPH.parent.mkdir(parents=True,exist_ok=True); OUT_GRAPH.write_text(json.dumps(graph,indent=2))

    resolved={}
    # Represent architectural nodes in the GitHub snapshot using valid generic PURLs.
    for e in edges:
        target=e['target']; version=e.get('resolved_sha') or sha[:12]
        p=purl_generic(target,version)
        resolved[p]={'package_url':p,'relationship':e.get('relationship','direct'),'scope':e.get('scope','runtime'),'metadata':{'dependency_class':e['class'],'observed':str(bool(e.get('observed'))).lower(),'source':e['source'][:255]}}
    snapshot={
      'version':0,'sha':sha,'ref':ref,
      'job':{'correlator':f"{os.environ.get('GITHUB_WORKFLOW','BRAINK Dependency Graph')}::{os.environ.get('GITHUB_JOB','detect-submit')}",'id':os.environ.get('GITHUB_RUN_ID','local'),'html_url':f"{os.environ.get('GITHUB_SERVER_URL','https://github.com')}/{os.environ.get('GITHUB_REPOSITORY','aboudykeddeh276-stack/BRAINK')}/actions/runs/{os.environ.get('GITHUB_RUN_ID','0')}"},
      'detector':{'name':'braink-kex-dependency-detector','version':'1.0.0','url':'https://github.com/aboudykeddeh276-stack/BRAINK','metadata':{'edge_classes':'PACKAGE,MODULE,REPOSITORY,RUNTIME_AUTHORITY'}},
      'scanned':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
      'manifests':{'braink-architecture':{'name':'BRAINK architectural/runtime dependencies','file':{'source_location':'.braink/dependency-edges.json'},'resolved':resolved}}
    }
    OUT_SNAPSHOT.write_text(json.dumps(snapshot,indent=2))
    print(json.dumps({'graph':str(OUT_GRAPH),'snapshot':str(OUT_SNAPSHOT),'edges':len(edges),'graph_cuts':len(cuts),'required_failures':len(required_fail)},indent=2))
    if required_fail: return 2
    return 0
if __name__=='__main__': sys.exit(main())
