#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, hmac, json, mimetypes, os, shutil, sqlite3, subprocess, tempfile, time, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get("KEX_SITES_DB",str(ROOT/"state"/"sites.sqlite3"))).expanduser()
STORE=Path(os.environ.get("KEX_SITES_STORE",str(ROOT/"state"/"objects"))).expanduser()
PUBLISH=Path(os.environ.get("KEX_SITES_PUBLISH_ROOT",str(ROOT/"state"/"published"))).expanduser()
UI=ROOT/"web"
TOKEN=os.environ.get("KEX_SITES_TOKEN","")
MAX_BODY=10*1024*1024

SCHEMA="""
PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sites(
 id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'SITE',
 state TEXT NOT NULL DEFAULT 'DRAFT', source_kind TEXT NOT NULL DEFAULT 'MANAGED',
 external_id TEXT, created_ns INTEGER NOT NULL, updated_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS domains(
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
 hostname TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'CUSTOM', state TEXT NOT NULL DEFAULT 'RECORDED',
 UNIQUE(site_id,hostname)
);
CREATE TABLE IF NOT EXISTS versions(
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL, source_sha256 TEXT NOT NULL, object_path TEXT NOT NULL,
 message TEXT NOT NULL, created_ns INTEGER NOT NULL, UNIQUE(site_id,ordinal)
);
CREATE TABLE IF NOT EXISTS deployments(
 id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
 version_id TEXT NOT NULL REFERENCES versions(id), adapter TEXT NOT NULL, state TEXT NOT NULL,
 target TEXT, readback TEXT NOT NULL DEFAULT '{}', created_ns INTEGER NOT NULL, updated_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, ts_ns INTEGER NOT NULL, actor TEXT NOT NULL, site_id TEXT,
 action TEXT NOT NULL, state TEXT NOT NULL, evidence TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL
);
"""

def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return time.time_ns()
def atomic_write(path:Path,data:bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".tmp-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        dfd=os.open(str(path.parent),os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

class Store:
    def __init__(self):
        DB.parent.mkdir(parents=True,exist_ok=True); STORE.mkdir(parents=True,exist_ok=True); PUBLISH.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(DB,check_same_thread=False); self.db.row_factory=sqlite3.Row; self.db.executescript(SCHEMA)
    def event(self,action,state,evidence,site_id=None,actor="owner"):
        r=self.db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone(); prev=r[0] if r else "GENESIS"
        ts=now(); body={"ts_ns":ts,"actor":actor,"site_id":site_id,"action":action,"state":state,"evidence":evidence,"prev_hash":prev}
        eh=sha(canon(body).encode()); self.db.execute("INSERT INTO events(ts_ns,actor,site_id,action,state,evidence,prev_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)",(ts,actor,site_id,action,state,canon(evidence),prev,eh)); self.db.commit()
        return {**body,"event_hash":eh}
    def sites(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM sites ORDER BY updated_ns DESC")]
    def site(self,sid):
        r=self.db.execute("SELECT * FROM sites WHERE id=? OR slug=?",(sid,sid)).fetchone()
        if not r:return None
        d=dict(r); d["domains"]=[dict(x) for x in self.db.execute("SELECT * FROM domains WHERE site_id=? ORDER BY hostname",(r["id"],))]
        d["versions"]=[dict(x) for x in self.db.execute("SELECT * FROM versions WHERE site_id=? ORDER BY ordinal DESC",(r["id"],))]
        d["deployments"]=[dict(x) for x in self.db.execute("SELECT * FROM deployments WHERE site_id=? ORDER BY created_ns DESC",(r["id"],))]
        for x in d["deployments"]: x["readback"]=json.loads(x["readback"])
        return d
    def create_site(self,p):
        slug=p["slug"].strip().lower(); 
        if not slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug): raise ValueError("invalid slug")
        sid=p.get("id") or "site_"+uuid.uuid4().hex; t=now()
        self.db.execute("INSERT INTO sites(id,slug,name,kind,state,source_kind,external_id,created_ns,updated_ns) VALUES(?,?,?,?,?,?,?,?,?)",(sid,slug,p.get("name") or slug,p.get("kind","SITE"),p.get("state","DRAFT"),p.get("source_kind","MANAGED"),p.get("external_id"),t,t)); self.db.commit()
        self.event("SITE_CREATE","COMMITTED",{"slug":slug,"external_id":p.get("external_id")},sid); return self.site(sid)
    def domain(self,sid,p):
        s=self.site(sid)
        if not s: raise KeyError("site")
        host=p["hostname"].strip().lower().rstrip("."); did="domain_"+uuid.uuid4().hex
        self.db.execute("INSERT OR REPLACE INTO domains(id,site_id,hostname,kind,state) VALUES(?,?,?,?,?)",(did,s["id"],host,p.get("kind","CUSTOM"),p.get("state","RECORDED"))); self.db.commit()
        self.event("DOMAIN_BIND","COMMITTED",{"hostname":host,"state":p.get("state","RECORDED")},s["id"]); return self.site(s["id"])
    def version(self,sid,p):
        s=self.site(sid)
        if not s: raise KeyError("site")
        files=p.get("files") or {}
        if not isinstance(files,dict) or not files: raise ValueError("files required")
        clean={}
        for name,text in files.items():
            q=Path(name)
            if q.is_absolute() or ".." in q.parts: raise ValueError("unsafe path")
            if not isinstance(text,str): raise ValueError("text files only")
            clean[q.as_posix()]=text
        payload=canon(clean).encode(); digest=sha(payload); vid="ver_"+uuid.uuid4().hex
        row=self.db.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM versions WHERE site_id=?",(s["id"],)).fetchone(); ordinal=row[0]
        obj=STORE/s["id"]/vid
        for name,text in clean.items(): atomic_write(obj/name,text.encode())
        manifest={"site_id":s["id"],"version_id":vid,"ordinal":ordinal,"source_sha256":digest,"files":{n:sha(v.encode()) for n,v in clean.items()}}
        atomic_write(obj/"manifest.json",(json.dumps(manifest,indent=2)+"\n").encode())
        self.db.execute("INSERT INTO versions(id,site_id,ordinal,source_sha256,object_path,message,created_ns) VALUES(?,?,?,?,?,?,?)",(vid,s["id"],ordinal,digest,str(obj),p.get("message",""),now()))
        self.db.execute("UPDATE sites SET updated_ns=?,state='VERSIONED' WHERE id=?",(now(),s["id"])); self.db.commit()
        self.event("VERSION_CREATE","COMMITTED",manifest,s["id"]); return self.site(s["id"])
    def deploy(self,sid,p):
        s=self.site(sid)
        if not s: raise KeyError("site")
        vid=p.get("version_id") or (s["versions"][0]["id"] if s["versions"] else None)
        if not vid: raise ValueError("no version")
        v=self.db.execute("SELECT * FROM versions WHERE id=? AND site_id=?",(vid,s["id"])).fetchone()
        if not v: raise ValueError("version not found")
        adapter=p.get("adapter","local"); dep="dep_"+uuid.uuid4().hex; t=now(); target=None; rb={}
        self.db.execute("INSERT INTO deployments(id,site_id,version_id,adapter,state,target,readback,created_ns,updated_ns) VALUES(?,?,?,?,?,?,?,?,?)",(dep,s["id"],vid,adapter,"RUNNING",None,"{}",t,t)); self.db.commit()
        try:
            if adapter=="local":
                dest=PUBLISH/s["slug"]
                stage=PUBLISH/(s["slug"]+".stage-"+dep)
                if stage.exists(): shutil.rmtree(stage)
                shutil.copytree(v["object_path"],stage,ignore=shutil.ignore_patterns("manifest.json"))
                if dest.exists(): shutil.rmtree(dest)
                os.replace(stage,dest); target=str(dest)
                rb={"exists":dest.exists(),"index_html":(dest/"index.html").exists(),"version_id":vid}
                state="DEPLOYED" if rb["exists"] else "FAILED"
            elif adapter=="command":
                cmd=os.environ.get("KEX_SITES_DEPLOY_CMD")
                if not cmd: raise RuntimeError("KEX_SITES_DEPLOY_CMD not configured")
                req={"site":s,"version":dict(v),"deployment_id":dep}
                cp=subprocess.run(cmd,shell=True,input=canon(req),text=True,capture_output=True,timeout=300)
                rb={"returncode":cp.returncode,"stdout":cp.stdout[-8000:],"stderr":cp.stderr[-8000:]}
                state="DEPLOYED" if cp.returncode==0 else "FAILED"; target=p.get("target")
            else: raise ValueError("unknown adapter")
        except Exception as e:
            state="FAILED"; rb={"error":str(e)}
        self.db.execute("UPDATE deployments SET state=?,target=?,readback=?,updated_ns=? WHERE id=?",(state,target,canon(rb),now(),dep))
        self.db.execute("UPDATE sites SET state=?,updated_ns=? WHERE id=?",("DEPLOYED" if state=="DEPLOYED" else "DEGRADED",now(),s["id"])); self.db.commit()
        self.event("DEPLOY",state,{"deployment_id":dep,"version_id":vid,"adapter":adapter,"target":target,"readback":rb},s["id"])
        return self.site(s["id"])
    def readback(self,sid,p):
        s=self.site(sid)
        if not s: raise KeyError("site")
        url=p.get("url")
        if not url: raise ValueError("url required")
        req=urllib.request.Request(url,method="GET",headers={"User-Agent":"BRAINK-KEX-Sites/1.0"})
        try:
            with urllib.request.urlopen(req,timeout=float(p.get("timeout",10))) as r:
                body=r.read(65536); out={"url":url,"status":r.status,"content_type":r.headers.get("content-type"),"bytes_sampled":len(body),"sha256_sample":sha(body),"pass":200<=r.status<400}
        except Exception as e: out={"url":url,"pass":False,"error":str(e)}
        self.event("PUBLIC_READBACK","PASS" if out["pass"] else "FAILED",out,s["id"]); return out
    def events(self,limit=200):
        rows=self.db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT ?",(limit,)).fetchall(); out=[]
        for r in rows:
            d=dict(r); d["evidence"]=json.loads(d["evidence"]); out.append(d)
        return out
    def verify(self):
        prev="GENESIS"; count=0
        for r in self.db.execute("SELECT * FROM events ORDER BY seq"):
            body={"ts_ns":r["ts_ns"],"actor":r["actor"],"site_id":r["site_id"],"action":r["action"],"state":r["state"],"evidence":json.loads(r["evidence"]),"prev_hash":r["prev_hash"]}
            if r["prev_hash"]!=prev or sha(canon(body).encode())!=r["event_hash"]: return {"ok":False,"seq":r["seq"]}
            prev=r["event_hash"]; count+=1
        return {"ok":True,"count":count,"head":prev}

S=Store()
class API(BaseHTTPRequestHandler):
    server_version="BRAINK-KEX-Sites/1.0"
    def log_message(self,fmt,*args): print(canon({"ts":time.time(),"remote":self.client_address[0],"message":fmt%args}))
    def sendj(self,code,obj):
        b=json.dumps(obj,indent=2).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>MAX_BODY: raise ValueError("body too large")
        return json.loads(self.rfile.read(n) or b"{}")
    def auth(self):
        if not TOKEN: return True
        v=self.headers.get("Authorization","")
        return v.startswith("Bearer ") and hmac.compare_digest(v[7:],TOKEN)
    def route(self):
        return [x for x in urlparse(self.path).path.split("/") if x]
    def do_GET(self):
        p=self.route()
        if p==["api","health"]: return self.sendj(200,{"ok":True,"service":"BRAINK_KEX_SITES","ledger":S.verify()})
        if p==["api","sites"]: return self.sendj(200,{"sites":S.sites()})
        if len(p)==3 and p[:2]==["api","sites"]:
            s=S.site(p[2]); return self.sendj(200,s) if s else self.sendj(404,{"error":"not found"})
        if p==["api","events"]: return self.sendj(200,{"events":S.events()})
        if p==["api","ledger","verify"]: return self.sendj(200,S.verify())
        rel="index.html" if not p else "/".join(p)
        f=(UI/rel).resolve()
        if UI.resolve() not in f.parents and f!=UI.resolve(): return self.sendj(403,{"error":"forbidden"})
        if not f.exists() or not f.is_file(): f=UI/"index.html"
        if not f.exists(): return self.sendj(404,{"error":"ui missing"})
        b=f.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(str(f))[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        if not self.auth(): return self.sendj(401,{"error":"unauthorized"})
        try:
            p=self.route(); b=self.body()
            if p==["api","sites"]: return self.sendj(201,S.create_site(b))
            if len(p)==4 and p[:2]==["api","sites"]:
                if p[3]=="domains": return self.sendj(200,S.domain(p[2],b))
                if p[3]=="versions": return self.sendj(200,S.version(p[2],b))
                if p[3]=="deploy": return self.sendj(200,S.deploy(p[2],b))
                if p[3]=="readback": return self.sendj(200,S.readback(p[2],b))
            return self.sendj(404,{"error":"route not found"})
        except KeyError as e:return self.sendj(404,{"error":str(e)})
        except (ValueError,json.JSONDecodeError) as e:return self.sendj(400,{"error":str(e)})
        except Exception as e:return self.sendj(500,{"error":str(e)})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--host",default=os.environ.get("KEX_SITES_HOST","127.0.0.1")); ap.add_argument("--port",type=int,default=int(os.environ.get("KEX_SITES_PORT","8787"))); a=ap.parse_args()
    print(canon({"service":"BRAINK_KEX_SITES","host":a.host,"port":a.port,"db":str(DB),"auth":"token" if TOKEN else "local-open"}))
    ThreadingHTTPServer((a.host,a.port),API).serve_forever()
if __name__=="__main__": main()
