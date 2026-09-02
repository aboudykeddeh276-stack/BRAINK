from pathlib import Path
import sqlite3,json,time,hashlib
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"))
def sha(v):return hashlib.sha256(canon(v).encode()).hexdigest()
class RuntimeRegistry:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);d=self.db();d.executescript("""
  CREATE TABLE IF NOT EXISTS runtimes(runtime_id TEXT PRIMARY KEY,runtime_class TEXT,command_route TEXT,argv_json TEXT,pid INTEGER,
  health_endpoint TEXT,dependencies_json TEXT,generation INTEGER,desired_state TEXT,observed_state TEXT,restart_count INTEGER,
  last_readback_json TEXT,last_failure TEXT,author_id TEXT,authorship_root TEXT,state_root TEXT,updated_ns INTEGER);
  CREATE TABLE IF NOT EXISTS receipts(seq INTEGER PRIMARY KEY AUTOINCREMENT,runtime_id TEXT,event TEXT,before_root TEXT,after_root TEXT,payload_json TEXT,created_ns INTEGER);
  """);d.commit();d.close()
 def db(self):
  d=sqlite3.connect(self.path);d.row_factory=sqlite3.Row;d.execute("PRAGMA journal_mode=WAL");d.execute("PRAGMA synchronous=FULL");return d
 def get(self,rid):
  d=self.db();r=d.execute("SELECT * FROM runtimes WHERE runtime_id=?",(rid,)).fetchone();d.close();return dict(r) if r else None
 def list(self):
  d=self.db();x=[dict(r) for r in d.execute("SELECT * FROM runtimes ORDER BY runtime_id")];d.close();return x
 def upsert(self,s):
  cur=self.get(s["runtime_id"]);before=cur["state_root"] if cur else None;now=time.time_ns()
  row={"runtime_id":s["runtime_id"],"runtime_class":s.get("runtime_class","PROCESS"),"command_route":s["command_route"],"argv_json":canon(s["argv"]),
       "pid":s.get("pid"),"health_endpoint":s.get("health_endpoint"),"dependencies_json":canon(s.get("dependencies",[])),
       "generation":int(s.get("generation",0)),"desired_state":s.get("desired_state","STOPPED"),"observed_state":s.get("observed_state","DEFINED"),
       "restart_count":int(s.get("restart_count",0)),"last_readback_json":canon(s.get("last_readback")) if s.get("last_readback") is not None else None,
       "last_failure":s.get("last_failure"),"author_id":s.get("author_id","AKD"),
       "authorship_root":s.get("authorship_root","enterprise/governance/AKD_AUTHORSHIP_ROOT.json"),"state_root":None,"updated_ns":now}
  row["state_root"]=sha({k:v for k,v in row.items() if k!="state_root"})
  d=self.db();d.execute("""INSERT INTO runtimes VALUES(:runtime_id,:runtime_class,:command_route,:argv_json,:pid,:health_endpoint,:dependencies_json,
  :generation,:desired_state,:observed_state,:restart_count,:last_readback_json,:last_failure,:author_id,:authorship_root,:state_root,:updated_ns)
  ON CONFLICT(runtime_id) DO UPDATE SET runtime_class=excluded.runtime_class,command_route=excluded.command_route,argv_json=excluded.argv_json,pid=excluded.pid,
  health_endpoint=excluded.health_endpoint,dependencies_json=excluded.dependencies_json,generation=excluded.generation,desired_state=excluded.desired_state,
  observed_state=excluded.observed_state,restart_count=excluded.restart_count,last_readback_json=excluded.last_readback_json,last_failure=excluded.last_failure,
  author_id=excluded.author_id,authorship_root=excluded.authorship_root,state_root=excluded.state_root,updated_ns=excluded.updated_ns""",row)
  d.execute("INSERT INTO receipts(runtime_id,event,before_root,after_root,payload_json,created_ns) VALUES(?,?,?,?,?,?)",(row["runtime_id"],"UPSERT",before,row["state_root"],canon(row),now));d.commit();d.close();return self.get(row["runtime_id"])
 def inflate(self,r):
  return {"runtime_id":r["runtime_id"],"runtime_class":r["runtime_class"],"command_route":r["command_route"],"argv":json.loads(r["argv_json"]),
          "pid":r["pid"],"health_endpoint":r["health_endpoint"],"dependencies":json.loads(r["dependencies_json"]),"generation":r["generation"],
          "desired_state":r["desired_state"],"observed_state":r["observed_state"],"restart_count":r["restart_count"],
          "last_readback":json.loads(r["last_readback_json"]) if r["last_readback_json"] else None,"last_failure":r["last_failure"],
          "author_id":r["author_id"],"authorship_root":r["authorship_root"]}
 def observe(self,rid,**kw):
  r=self.get(rid)
  if not r:raise KeyError(rid)
  s=self.inflate(r);s.update({k:v for k,v in kw.items() if v is not None or k=="pid"});return self.upsert(s)
 def set_desired(self,rid,state):
  r=self.get(rid);s=self.inflate(r);s["desired_state"]=state;return self.upsert(s)
