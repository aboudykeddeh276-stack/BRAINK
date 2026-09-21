#!/usr/bin/env python3
"""BRAINK Owner Control Bridge.

Owner-controlled registry and execution boundary for persistent projects.
No provider operation is reported as executed unless a registered adapter
returns readback evidence.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS projects(
 project_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL,
 locator TEXT NOT NULL, source_repo TEXT, runtime_id TEXT, deployment_id TEXT,
 state TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS capabilities(
 project_id TEXT NOT NULL, provider TEXT NOT NULL, capability TEXT NOT NULL,
 endpoint TEXT, authority TEXT NOT NULL, state TEXT NOT NULL,
 PRIMARY KEY(project_id,provider,capability)
);
CREATE TABLE IF NOT EXISTS receipts(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, project_id TEXT NOT NULL,
 action TEXT NOT NULL, state TEXT NOT NULL, evidence TEXT NOT NULL,
 prev_hash TEXT NOT NULL, receipt_hash TEXT NOT NULL
);
"""

def canonical(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",",":"), ensure_ascii=False)

class Bridge:
    def __init__(self, db: str):
        self.path=Path(db).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cx=sqlite3.connect(self.path)
        self.cx.executescript(SCHEMA)

    def receipt(self, project_id:str, action:str, state:str, evidence:Dict[str,Any]):
        row=self.cx.execute("SELECT receipt_hash FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
        prev=row[0] if row else "GENESIS"
        ts=time.time_ns()
        body={"ts":ts,"project_id":project_id,"action":action,"state":state,
              "evidence":evidence,"prev_hash":prev}
        h=hashlib.sha256(canonical(body).encode()).hexdigest()
        self.cx.execute("INSERT INTO receipts(ts,project_id,action,state,evidence,prev_hash,receipt_hash) VALUES(?,?,?,?,?,?,?)",
                        (ts,project_id,action,state,canonical(evidence),prev,h))
        self.cx.commit()
        return {**body,"receipt_hash":h}

    def register(self, p:Dict[str,Any]):
        now=time.time_ns()
        self.cx.execute("""INSERT INTO projects(project_id,owner_id,kind,locator,source_repo,runtime_id,deployment_id,state,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET
        owner_id=excluded.owner_id,kind=excluded.kind,locator=excluded.locator,
        source_repo=COALESCE(excluded.source_repo,projects.source_repo),
        runtime_id=COALESCE(excluded.runtime_id,projects.runtime_id),
        deployment_id=COALESCE(excluded.deployment_id,projects.deployment_id),
        state=excluded.state,updated_at=excluded.updated_at""",
        (p["project_id"],p["owner_id"],p["kind"],p["locator"],p.get("source_repo"),
         p.get("runtime_id"),p.get("deployment_id"),p.get("state","REGISTERED"),now,now))
        self.cx.commit()
        return self.receipt(p["project_id"],"REGISTER_PROJECT","COMMITTED",p)

    def capability(self, project_id:str, provider:str, capability:str, authority:str, state:str, endpoint:Optional[str]=None):
        self.cx.execute("""INSERT INTO capabilities(project_id,provider,capability,endpoint,authority,state)
        VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,provider,capability) DO UPDATE SET
        endpoint=excluded.endpoint,authority=excluded.authority,state=excluded.state""",
        (project_id,provider,capability,endpoint,authority,state))
        self.cx.commit()
        return self.receipt(project_id,"BIND_CAPABILITY","COMMITTED",
                            {"provider":provider,"capability":capability,"authority":authority,"state":state,"endpoint":endpoint})

    def status(self, project_id:str):
        p=self.cx.execute("SELECT project_id,owner_id,kind,locator,source_repo,runtime_id,deployment_id,state FROM projects WHERE project_id=?",(project_id,)).fetchone()
        if not p: raise SystemExit("unknown project")
        caps=self.cx.execute("SELECT provider,capability,endpoint,authority,state FROM capabilities WHERE project_id=? ORDER BY provider,capability",(project_id,)).fetchall()
        return {"project":dict(zip(["project_id","owner_id","kind","locator","source_repo","runtime_id","deployment_id","state"],p)),
                "capabilities":[dict(zip(["provider","capability","endpoint","authority","state"],x)) for x in caps]}

    def verify(self):
        prev="GENESIS"
        rows=self.cx.execute("SELECT ts,project_id,action,state,evidence,prev_hash,receipt_hash FROM receipts ORDER BY seq").fetchall()
        for ts,p,a,s,e,ph,rh in rows:
            body={"ts":ts,"project_id":p,"action":a,"state":s,"evidence":json.loads(e),"prev_hash":ph}
            expected=hashlib.sha256(canonical(body).encode()).hexdigest()
            if ph!=prev or rh!=expected: return {"ok":False,"count":len(rows),"failed":p}
            prev=rh
        return {"ok":True,"count":len(rows),"head":prev}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default=os.environ.get("BRAINK_OWNER_DB","~/.braink/owner-control.sqlite3"))
    sp=ap.add_subparsers(dest="cmd",required=True)
    r=sp.add_parser("register"); r.add_argument("--manifest",required=True)
    c=sp.add_parser("capability"); c.add_argument("--project",required=True); c.add_argument("--provider",required=True); c.add_argument("--capability",required=True); c.add_argument("--authority",required=True); c.add_argument("--state",required=True); c.add_argument("--endpoint")
    s=sp.add_parser("status"); s.add_argument("--project",required=True)
    sp.add_parser("verify")
    args=ap.parse_args(); b=Bridge(args.db)
    if args.cmd=="register":
        out=b.register(json.loads(Path(args.manifest).read_text()))
    elif args.cmd=="capability":
        out=b.capability(args.project,args.provider,args.capability,args.authority,args.state,args.endpoint)
    elif args.cmd=="status": out=b.status(args.project)
    else: out=b.verify()
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=="__main__": main()
