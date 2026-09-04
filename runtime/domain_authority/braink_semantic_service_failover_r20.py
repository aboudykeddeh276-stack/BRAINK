from pathlib import Path
import json, sqlite3, hashlib, threading, time, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB=Path("/mnt/data/BRAINK_R20_SEMANTIC_SERVICE_REGISTRY.sqlite")
DOMAIN="keddeh.com"
DOMAIN_ID="LEX://DOMAIN/keddeh.com"
SERVICE_ID="LEX://SERVER/GLOBAL"

def canon(o): return json.dumps(o,sort_keys=True,separators=(",",":"))
def sha(o): return hashlib.sha256(canon(o).encode()).hexdigest()

def init_db():
    c=sqlite3.connect(DB)
    x=c.cursor()
    x.execute("""CREATE TABLE IF NOT EXISTS semantic_domains(
      domain TEXT PRIMARY KEY, canonical_id TEXT NOT NULL, service_id TEXT NOT NULL,
      lineage_id TEXT NOT NULL, state TEXT NOT NULL, proof_sha256 TEXT NOT NULL)""")
    x.execute("""CREATE TABLE IF NOT EXISTS service_carriers(
      service_id TEXT NOT NULL, machine_id TEXT NOT NULL, braink_id TEXT NOT NULL,
      lineage_id TEXT NOT NULL, vector_id TEXT NOT NULL, endpoint TEXT NOT NULL,
      priority INTEGER NOT NULL, state TEXT NOT NULL,
      PRIMARY KEY(service_id,machine_id))""")
    binding={
      "domain":DOMAIN,"canonical_id":DOMAIN_ID,"service_id":SERVICE_ID,
      "lineage_id":"BRAINK::LINEAGE::DOMAIN::KEDDEH::GENESIS","state":"ACTIVE"
    }
    proof=sha(binding)
    x.execute("INSERT OR REPLACE INTO semantic_domains VALUES(?,?,?,?,?,?)",
              (DOMAIN,DOMAIN_ID,SERVICE_ID,binding["lineage_id"],"ACTIVE",proof))
    rows=[
      (SERVICE_ID,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R20",
       "BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS","VEC://M1/SERVER/17951",
       "http://127.0.0.1:17951",10,"ACTIVE"),
      (SERVICE_ID,"KEX-MACHINE-002","BRAINK::KEX-MACHINE-002::R20",
       "BRAINK::LINEAGE::KEX-MACHINE-002::GENESIS","VEC://M2/SERVER/17952",
       "http://127.0.0.1:17952",20,"ACTIVE"),
    ]
    x.executemany("INSERT OR REPLACE INTO service_carriers VALUES(?,?,?,?,?,?,?,?)",rows)
    c.commit(); c.close()

class H(BaseHTTPRequestHandler):
    machine_id=""; braink_id=""; lineage_id=""
    def do_GET(self):
        if self.path!="/health":
            self.send_response(404); self.end_headers(); return
        raw=json.dumps({
          "status":"PASS","machine_id":self.machine_id,
          "braink_id":self.braink_id,"lineage_id":self.lineage_id,
          "service_id":SERVICE_ID
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers(); self.wfile.write(raw)
    def log_message(self,*a): pass

def make_server(port,machine,braink,lineage):
    cls=type(f"H_{port}",(H,),{"machine_id":machine,"braink_id":braink,"lineage_id":lineage})
    s=ThreadingHTTPServer(("127.0.0.1",port),cls)
    t=threading.Thread(target=s.serve_forever,daemon=True); t.start()
    return s

def resolve_domain(domain):
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    d=c.execute("SELECT * FROM semantic_domains WHERE domain=?",(domain,)).fetchone()
    if not d:
        c.close(); return {"status":"MISS"}
    d=dict(d)
    rows=[dict(r) for r in c.execute(
      "SELECT * FROM service_carriers WHERE service_id=? AND state='ACTIVE' ORDER BY priority",
      (d["service_id"],)).fetchall()]
    c.close()
    attempts=[]
    for r in rows:
        try:
            with urllib.request.urlopen(r["endpoint"]+"/health",timeout=.5) as resp:
                h=json.loads(resp.read())
            if h.get("status")=="PASS" and h.get("service_id")==d["service_id"]:
                return {
                  "status":"PASS","canonical_id":d["canonical_id"],
                  "service_id":d["service_id"],"domain_lineage":d["lineage_id"],
                  "domain_proof_sha256":d["proof_sha256"],
                  "selected_carrier":r,"health":h,"attempts":attempts
                }
        except Exception as e:
            attempts.append({"machine_id":r["machine_id"],"endpoint":r["endpoint"],
                             "status":"FAIL","error":type(e).__name__})
    return {"status":"UNREACHABLE","canonical_id":d["canonical_id"],
            "service_id":d["service_id"],"attempts":attempts}

def main():
    init_db()
    s1=make_server(17951,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R20",
                   "BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS")
    s2=make_server(17952,"KEX-MACHINE-002","BRAINK::KEX-MACHINE-002::R20",
                   "BRAINK::LINEAGE::KEX-MACHINE-002::GENESIS")
    time.sleep(.15)
    first=resolve_domain(DOMAIN)
    s1.shutdown(); s1.server_close(); time.sleep(.1)
    failover=resolve_domain(DOMAIN)
    s1r=make_server(17951,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R20",
                    "BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS")
    time.sleep(.15)
    restored=resolve_domain(DOMAIN)
    checks={
      "semantic_domain_resolves":first["status"]=="PASS",
      "primary_selected_initially":first["selected_carrier"]["machine_id"]=="KEX-MACHINE-001",
      "same_canonical_domain_after_failover":failover.get("canonical_id")==DOMAIN_ID,
      "same_service_identity_after_failover":failover.get("service_id")==SERVICE_ID,
      "secondary_selected_after_primary_loss":failover.get("selected_carrier",{}).get("machine_id")=="KEX-MACHINE-002",
      "machine_identity_distinct":first["health"]["machine_id"]!=failover["health"]["machine_id"],
      "machine_lineage_distinct":first["health"]["lineage_id"]!=failover["health"]["lineage_id"],
      "domain_identity_does_not_change_with_carrier":first["canonical_id"]==failover["canonical_id"],
      "primary_reselected_after_restore":restored.get("selected_carrier",{}).get("machine_id")=="KEX-MACHINE-001",
    }
    receipt={
      "schema":"braink.semantic-service-failover.r20",
      "contract":"CANONICAL_DOMAIN_TO_SERVICE_ID_TO_HEALTHY_CARRIER",
      "domain":DOMAIN,"canonical_id":DOMAIN_ID,"service_id":SERVICE_ID,
      "initial":first,"failover":failover,"restored":restored,
      "checks":checks,"status":"PASS" if all(checks.values()) else "FAIL"
    }
    Path("/mnt/data/BRAINK_R20_SEMANTIC_SERVICE_FAILOVER_RECEIPT.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    s1r.shutdown(); s1r.server_close(); s2.shutdown(); s2.server_close()
    return 0 if receipt["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
