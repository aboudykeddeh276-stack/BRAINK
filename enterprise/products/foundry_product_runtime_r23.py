from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import sqlite3,json,time,uuid,hashlib

def sha(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class ProductStore:
    def __init__(self,path):self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def db(self):
        d=sqlite3.connect(self.path);d.row_factory=sqlite3.Row;d.execute("PRAGMA journal_mode=WAL");d.execute("PRAGMA synchronous=FULL");return d
    def _init(self):
        d=self.db();d.executescript("""
        CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,customer_id TEXT,name TEXT NOT NULL,state TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,workspace_id TEXT,name TEXT NOT NULL,content TEXT NOT NULL,content_hash TEXT NOT NULL,revision INTEGER NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY,customer_id TEXT,name TEXT NOT NULL,domain TEXT NOT NULL,state TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY,site_id TEXT NOT NULL,slug TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,revision INTEGER NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,source_type TEXT NOT NULL,source_id TEXT NOT NULL,state TEXT NOT NULL,content_root TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,action TEXT NOT NULL,target_id TEXT NOT NULL,evidence_root TEXT NOT NULL,created_ns INTEGER NOT NULL);
        """);d.commit();d.close()
    def create_customer(self,name):
        i="CUS-"+uuid.uuid4().hex[:12];n=time.time_ns();d=self.db();d.execute("INSERT INTO customers VALUES(?,?,?)",(i,name,n));d.commit();d.close();return {"id":i,"name":name}
    def create_workspace(self,customer_id,name):
        i="WS-"+uuid.uuid4().hex[:12];n=time.time_ns();d=self.db();d.execute("INSERT INTO workspaces VALUES(?,?,?,?,?)",(i,customer_id,name,"ACTIVE",n));d.commit();d.close();return {"id":i,"customer_id":customer_id,"name":name,"state":"ACTIVE"}
    def write_file(self,workspace_id,name,content):
        d=self.db();prev=d.execute("SELECT MAX(revision) FROM files WHERE workspace_id=? AND name=?",(workspace_id,name)).fetchone()[0] or 0;i="FIL-"+uuid.uuid4().hex[:12];n=time.time_ns();h=hashlib.sha256(content.encode()).hexdigest();d.execute("INSERT INTO files VALUES(?,?,?,?,?,?,?)",(i,workspace_id,name,content,h,prev+1,n));d.commit();d.close();return {"id":i,"revision":prev+1,"sha256":h}
    def create_site(self,customer_id,name,domain):
        i="SITE-"+uuid.uuid4().hex[:12];n=time.time_ns();d=self.db();d.execute("INSERT INTO sites VALUES(?,?,?,?,?,?)",(i,customer_id,name,domain,"DRAFT",n));d.commit();d.close();return {"id":i,"domain":domain,"state":"DRAFT"}
    def put_page(self,site_id,slug,title,body):
        d=self.db();prev=d.execute("SELECT MAX(revision) FROM pages WHERE site_id=? AND slug=?",(site_id,slug)).fetchone()[0] or 0;i="PAGE-"+uuid.uuid4().hex[:12];n=time.time_ns();d.execute("INSERT INTO pages VALUES(?,?,?,?,?,?,?)",(i,site_id,slug,title,body,prev+1,n));d.commit();d.close();return {"id":i,"slug":slug,"revision":prev+1}
    def publish_site(self,site_id):
        d=self.db();rows=d.execute("SELECT slug,title,body,revision FROM pages WHERE site_id=? ORDER BY slug,revision",(site_id,)).fetchall();latest={}
        for r in rows:latest[r["slug"]]=dict(r)
        content={"site_id":site_id,"pages":latest};cr=sha(content);pid="PUB-"+uuid.uuid4().hex[:12];n=time.time_ns();d.execute("INSERT INTO publications VALUES(?,?,?,?,?,?)",(pid,"SITE",site_id,"QUALIFIED_LOCAL",cr,n));d.execute("UPDATE sites SET state='QUALIFIED_LOCAL' WHERE id=?",(site_id,));rid="RCT-"+uuid.uuid4().hex[:12];d.execute("INSERT INTO receipts VALUES(?,?,?,?,?)",(rid,"publish_site",site_id,cr,n));d.commit();d.close();return {"publication_id":pid,"receipt_id":rid,"state":"QUALIFIED_LOCAL","content_root":cr,"page_count":len(latest)}
    def state(self):
        d=self.db();out={t:d.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("customers","workspaces","files","sites","pages","publications","receipts")};d.close();out["state_root"]=sha(out);return out

class API:
    def __init__(self,store):self.store=store
    def handler(self):
        store=self.store
        class H(BaseHTTPRequestHandler):
            def sendj(self,code,obj):
                raw=json.dumps(obj).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
            def body(self):
                n=int(self.headers.get("Content-Length","0"));return json.loads(self.rfile.read(n) or b"{}")
            def do_GET(self):
                if self.path=="/health":return self.sendj(200,{"status":"OK","service":"KEDDEH_FOUNDRY_PRODUCT_RUNTIME_R23"})
                if self.path=="/state":return self.sendj(200,store.state())
                return self.sendj(404,{"status":"NOT_FOUND"})
            def do_POST(self):
                p=urlparse(self.path).path;b=self.body()
                try:
                    if p=="/customers":o=store.create_customer(b["name"])
                    elif p=="/workspaces":o=store.create_workspace(b["customer_id"],b["name"])
                    elif p=="/files":o=store.write_file(b["workspace_id"],b["name"],b["content"])
                    elif p=="/sites":o=store.create_site(b["customer_id"],b["name"],b["domain"])
                    elif p=="/pages":o=store.put_page(b["site_id"],b["slug"],b["title"],b["body"])
                    elif p=="/publish/site":o=store.publish_site(b["site_id"])
                    else:return self.sendj(404,{"status":"NOT_FOUND"})
                    return self.sendj(200,o)
                except Exception as e:return self.sendj(400,{"status":"ERROR","error":type(e).__name__})
            def log_message(self,*_):pass
        return H

def serve(db_path="runtime/foundry_products.sqlite3",host="127.0.0.1",port=19520):ThreadingHTTPServer((host,port),API(ProductStore(db_path)).handler()).serve_forever()
if __name__=="__main__":serve()
