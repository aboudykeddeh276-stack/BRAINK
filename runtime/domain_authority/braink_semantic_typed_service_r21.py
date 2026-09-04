from pathlib import Path
import json, sqlite3, hashlib, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT=Path("/mnt/data")
REG=ROOT/"BRAINK_R21_REGISTRY.sqlite"
DOMAIN="keddeh.com"
DOMAIN_ID="LEX://DOMAIN/keddeh.com"
SERVICE_ID="LEX://SERVER/GLOBAL"

def sha_text(s): return hashlib.sha256(s.encode()).hexdigest()

def init_registry():
    c=sqlite3.connect(REG); x=c.cursor()
    x.execute("""CREATE TABLE IF NOT EXISTS domains(
      domain TEXT PRIMARY KEY, canonical_id TEXT, service_id TEXT, proof_sha256 TEXT)""")
    x.execute("""CREATE TABLE IF NOT EXISTS carriers(
      service_id TEXT,machine_id TEXT,braink_id TEXT,lineage_id TEXT,
      vector_id TEXT,endpoint TEXT,priority INTEGER,state TEXT,
      PRIMARY KEY(service_id,machine_id))""")
    proof=sha_text(json.dumps({"domain":DOMAIN,"canonical_id":DOMAIN_ID,"service_id":SERVICE_ID},sort_keys=True))
    x.execute("INSERT OR REPLACE INTO domains VALUES(?,?,?,?)",(DOMAIN,DOMAIN_ID,SERVICE_ID,proof))
    x.executemany("INSERT OR REPLACE INTO carriers VALUES(?,?,?,?,?,?,?,?)",[
      (SERVICE_ID,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R21","LINEAGE::M1",
       "VEC://M1/SERVER/17961","http://127.0.0.1:17961",10,"ACTIVE"),
      (SERVICE_ID,"KEX-MACHINE-002","BRAINK::KEX-MACHINE-002::R21","LINEAGE::M2",
       "VEC://M2/SERVER/17962","http://127.0.0.1:17962",20,"ACTIVE"),
    ])
    c.commit(); c.close()

def machine_db(mid): return ROOT/f"BRAINK_R21_{mid}.sqlite"

def init_machine_db(mid):
    c=sqlite3.connect(machine_db(mid))
    c.execute("""CREATE TABLE IF NOT EXISTS cloud_objects(
      object_id TEXT PRIMARY KEY,payload TEXT,payload_sha256 TEXT,revision INTEGER,lineage_id TEXT,state TEXT)""")
    c.commit(); c.close()

def upsert_obj(mid,obj):
    c=sqlite3.connect(machine_db(mid))
    c.execute("INSERT OR REPLACE INTO cloud_objects VALUES(?,?,?,?,?,?)",
              (obj["object_id"],obj["payload"],obj["payload_sha256"],obj["revision"],obj["lineage_id"],obj["state"]))
    c.commit(); c.close()

def get_obj(mid,oid):
    c=sqlite3.connect(machine_db(mid)); c.row_factory=sqlite3.Row
    r=c.execute("SELECT * FROM cloud_objects WHERE object_id=?",(oid,)).fetchone()
    c.close(); return dict(r) if r else None

class H(BaseHTTPRequestHandler):
    machine_id=""; braink_id=""; lineage_id=""
    def sendj(self,status,obj):
        raw=json.dumps(obj,sort_keys=True).encode()
        self.send_response(status); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path=="/health":
            return self.sendj(200,{"status":"PASS","machine_id":self.machine_id,"braink_id":self.braink_id,
                                   "lineage_id":self.lineage_id,"service_id":SERVICE_ID})
        if self.path.startswith("/cloud/read?"):
            from urllib.parse import urlparse,parse_qs
            oid=parse_qs(urlparse(self.path).query).get("object_id",[""])[0]
            obj=get_obj(self.machine_id,oid)
            if not obj: return self.sendj(404,{"status":"NOT_FOUND","object_id":oid})
            return self.sendj(200,{"status":"PASS","machine_id":self.machine_id,"object":obj})
        return self.sendj(404,{"status":"NOT_FOUND"})
    def do_POST(self):
        if self.path!="/cloud/write": return self.sendj(404,{"status":"NOT_FOUND"})
        n=int(self.headers.get("Content-Length","0")); body=json.loads(self.rfile.read(n) or b"{}")
        prior=get_obj(self.machine_id,body["object_id"])
        rev=(prior["revision"] if prior else 0)+1
        obj={"object_id":body["object_id"],"payload":body["payload"],"payload_sha256":sha_text(body["payload"]),
             "revision":rev,"lineage_id":self.lineage_id,"state":"COMMITTED"}
        upsert_obj(self.machine_id,obj)
        return self.sendj(200,{"status":"PASS","machine_id":self.machine_id,"object":obj})
    def log_message(self,*a): pass

def server(port,mid,bid,lid):
    cls=type(f"H_{mid}",(H,),{"machine_id":mid,"braink_id":bid,"lineage_id":lid})
    s=ThreadingHTTPServer(("127.0.0.1",port),cls)
    threading.Thread(target=s.serve_forever,daemon=True).start(); return s

def resolve():
    c=sqlite3.connect(REG); c.row_factory=sqlite3.Row
    d=dict(c.execute("SELECT * FROM domains WHERE domain=?",(DOMAIN,)).fetchone())
    carriers=[dict(r) for r in c.execute("SELECT * FROM carriers WHERE service_id=? AND state='ACTIVE' ORDER BY priority",
                                         (d["service_id"],))]
    c.close()
    attempts=[]
    for r in carriers:
        try:
            with urllib.request.urlopen(r["endpoint"]+"/health",timeout=.4) as z: h=json.loads(z.read())
            if h["status"]=="PASS":
                return {"status":"PASS","canonical_id":d["canonical_id"],"service_id":d["service_id"],
                        "domain_proof_sha256":d["proof_sha256"],"carrier":r,"health":h,"attempts":attempts}
        except Exception as e:
            attempts.append({"machine_id":r["machine_id"],"status":"FAIL","error":type(e).__name__})
    return {"status":"UNREACHABLE","canonical_id":d["canonical_id"],"service_id":d["service_id"],"attempts":attempts}

def routed_post(path,obj):
    r=resolve(); ep=r["carrier"]["endpoint"]
    req=urllib.request.Request(ep+path,data=json.dumps(obj).encode(),
                               headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=1) as z: return r,json.loads(z.read())

def routed_get(path):
    r=resolve(); ep=r["carrier"]["endpoint"]
    with urllib.request.urlopen(ep+path,timeout=1) as z: return r,json.loads(z.read())

def replicate(src,dst,oid):
    obj=get_obj(src,oid)
    replica=dict(obj); replica["lineage_id"]="LINEAGE::M2" if dst=="KEX-MACHINE-002" else "LINEAGE::M1"
    replica["state"]="REPLICA_COMMITTED"
    upsert_obj(dst,replica)

def reconcile(src,dst,oid):
    obj=get_obj(src,oid)
    merged=dict(obj); merged["lineage_id"]="LINEAGE::M1" if dst=="KEX-MACHINE-001" else "LINEAGE::M2"
    merged["state"]="RECONCILED"
    upsert_obj(dst,merged)

def main():
    init_registry()
    for mid in ("KEX-MACHINE-001","KEX-MACHINE-002"): init_machine_db(mid)
    s1=server(17961,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R21","LINEAGE::M1")
    s2=server(17962,"KEX-MACHINE-002","BRAINK::KEX-MACHINE-002::R21","LINEAGE::M2")
    time.sleep(.12)

    route1,w1=routed_post("/cloud/write",{"object_id":"CLOUD-R21-001","payload":"BRAINK semantic routed object v1"})
    replicate("KEX-MACHINE-001","KEX-MACHINE-002","CLOUD-R21-001")

    s1.shutdown(); s1.server_close(); time.sleep(.08)
    route2,r2=routed_get("/cloud/read?object_id=CLOUD-R21-001")
    route3,w2=routed_post("/cloud/write",{"object_id":"CLOUD-R21-001","payload":"BRAINK semantic routed object v2"})
    failover_obj=get_obj("KEX-MACHINE-002","CLOUD-R21-001")

    s1r=server(17961,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R21","LINEAGE::M1")
    reconcile("KEX-MACHINE-002","KEX-MACHINE-001","CLOUD-R21-001")
    time.sleep(.08)
    route4,r4=routed_get("/cloud/read?object_id=CLOUD-R21-001")
    m1=get_obj("KEX-MACHINE-001","CLOUD-R21-001"); m2=get_obj("KEX-MACHINE-002","CLOUD-R21-001")

    checks={
      "initial_write_via_semantic_route":w1["status"]=="PASS" and route1["carrier"]["machine_id"]=="KEX-MACHINE-001",
      "same_domain_identity_on_failover":route2["canonical_id"]==DOMAIN_ID,
      "secondary_read_after_primary_loss":r2["status"]=="PASS" and route2["carrier"]["machine_id"]=="KEX-MACHINE-002",
      "secondary_write_after_primary_loss":w2["status"]=="PASS" and route3["carrier"]["machine_id"]=="KEX-MACHINE-002",
      "revision_advanced_on_secondary":failover_obj["revision"]==2,
      "primary_reselected_after_restore":route4["carrier"]["machine_id"]=="KEX-MACHINE-001",
      "reconciled_payload_hash_equal":m1["payload_sha256"]==m2["payload_sha256"],
      "reconciled_revision_equal":m1["revision"]==m2["revision"]==2,
      "lineage_remains_distinct":m1["lineage_id"]!=m2["lineage_id"],
      "canonical_domain_never_changed":all(r["canonical_id"]==DOMAIN_ID for r in (route1,route2,route3,route4)),
    }
    receipt={"schema":"braink.semantic-typed-service.r21",
             "contract":"DOMAIN_IDENTITY_TO_TYPED_SERVICE_TO_REPLICATED_OBJECT_WITH_FAILOVER",
             "canonical_id":DOMAIN_ID,"service_id":SERVICE_ID,
             "initial_route":route1,"failover_read_route":route2,"failover_write_route":route3,
             "restored_route":route4,"m1_object":m1,"m2_object":m2,
             "checks":checks,"status":"PASS" if all(checks.values()) else "FAIL"}
    Path("/mnt/data/BRAINK_R21_SEMANTIC_TYPED_SERVICE_RECEIPT.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    s1r.shutdown(); s1r.server_close(); s2.shutdown(); s2.server_close()
    return 0 if receipt["status"]=="PASS" else 2

if __name__=="__main__": raise SystemExit(main())
