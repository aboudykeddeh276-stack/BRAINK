from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import sqlite3, json, hashlib, time

ROOT=Path(__file__).resolve().parent

def canon(v:Any)->str:
    return json.dumps(v,sort_keys=True,separators=(",",":"))

def sha(v:Any)->str:
    return hashlib.sha256(canon(v).encode()).hexdigest()

class FoundryExecutor:
    GROUPS=("research","runtime","verification","evolution","proof")
    STAGES=("DISCOVER","RESEARCH","DESIGN","IMPLEMENT","TEST","QUALIFY","DEPLOY","OBSERVE","RECONCILE","EVOLVE")

    def __init__(self, db_path: str|Path):
        self.db_path=Path(db_path);self.db_path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def _db(self):
        db=sqlite3.connect(self.db_path);db.row_factory=sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL");db.execute("PRAGMA synchronous=FULL");return db
    def _init(self):
        db=self._db();db.executescript("""
        CREATE TABLE IF NOT EXISTS work(work_module_id TEXT PRIMARY KEY,foundry TEXT NOT NULL,process TEXT NOT NULL,stage TEXT NOT NULL,state TEXT NOT NULL,vfs_address TEXT NOT NULL,instruction TEXT NOT NULL,epoch INTEGER NOT NULL,updated_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS assignments(assignment_id TEXT PRIMARY KEY,work_module_id TEXT NOT NULL,agent_group TEXT NOT NULL,supervisor TEXT NOT NULL,authority_scope TEXT NOT NULL,epoch INTEGER NOT NULL,state TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS holes(hole_id TEXT PRIMARY KEY,work_module_id TEXT NOT NULL,class TEXT NOT NULL,requirement TEXT NOT NULL,state TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS receipts(receipt_id TEXT PRIMARY KEY,work_module_id TEXT NOT NULL,stage TEXT NOT NULL,status TEXT NOT NULL,evidence_root TEXT NOT NULL,created_ns INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS continuation(foundry TEXT PRIMARY KEY,current_work_module TEXT,completed_count INTEGER NOT NULL,state_root TEXT NOT NULL,updated_ns INTEGER NOT NULL);
        """);db.commit();db.close()
    def hydrate(self, queue_path: str|Path):
        q=json.loads(Path(queue_path).read_text())["work_modules"];db=self._db();now=time.time_ns()
        for w in q:
            db.execute("INSERT OR IGNORE INTO work VALUES(?,?,?,?,?,?,?,?,?)",(w["work_module_id"],w["foundry"],w["process"],"DISCOVER","READY",w["vfs_address"],w["instruction"],1,now))
            for group in self.GROUPS:
                aid=f"ASN-{w['work_module_id']}-{group}"
                db.execute("INSERT OR IGNORE INTO assignments VALUES(?,?,?,?,?,?,?,?)",(aid,w["work_module_id"],group,f"supervisor://{w['foundry']}/{group}",f"{w['foundry']}:{w['process']}:{group}",1,"ASSIGNED",now))
        db.commit();db.close();return {"work_modules":len(q),"assignments":len(q)*len(self.GROUPS)}
    def open_hole(self,work_module_id:str,klass:str,requirement:str):
        hid="HOLE-"+sha({"wm":work_module_id,"class":klass,"requirement":requirement})[:16];db=self._db();now=time.time_ns()
        db.execute("INSERT OR IGNORE INTO holes VALUES(?,?,?,?,?,?)",(hid,work_module_id,klass,requirement,"OPEN",now));db.commit();db.close();return hid
    def advance(self,work_module_id:str,stage:str,status:str,evidence:Dict[str,Any]):
        if stage not in self.STAGES: raise ValueError("INVALID_STAGE")
        db=self._db();now=time.time_ns();row=db.execute("SELECT 1 FROM work WHERE work_module_id=?",(work_module_id,)).fetchone()
        if not row: raise KeyError(work_module_id)
        rid="RCT-"+sha({"wm":work_module_id,"stage":stage,"evidence":evidence,"n":now})[:16];er=sha(evidence)
        db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?)",(rid,work_module_id,stage,status,er,now));db.execute("UPDATE work SET stage=?,state=?,updated_ns=? WHERE work_module_id=?",(stage,status,now,work_module_id));db.commit();db.close();return {"receipt_id":rid,"evidence_root":er}
    def seed_capability_holes(self, corpus_path: str|Path):
        corpus=json.loads(Path(corpus_path).read_text())["foundries"];queue=json.loads((ROOT/"FOUNDRY_WORK_QUEUE_R22.json").read_text())["work_modules"];by={(w["foundry"],w["process"]):w for w in queue};created=0
        for fid,cfg in corpus.items():
            for process in cfg["processes"]:
                self.open_hole(by[(fid,process)]["work_module_id"],"IMPLEMENTATION",f"Executable implementation for {fid}.{process}");created+=1
            anchor=by[(fid,cfg["processes"][0])]
            for server in cfg["servers"]:
                self.open_hole(anchor["work_module_id"],"SERVER_BINDING",f"Qualify and bind server family {server} for {fid}");created+=1
        return created
    def snapshot(self):
        db=self._db();counts={t:db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("work","assignments","holes","receipts","continuation")};open_holes=db.execute("SELECT COUNT(*) FROM holes WHERE state='OPEN'").fetchone()[0];stages={r[0]:r[1] for r in db.execute("SELECT stage,COUNT(*) FROM work GROUP BY stage")};db.close();state={"counts":counts,"open_holes":open_holes,"stages":stages};state["state_root"]=sha(state);return state
    def checkpoint_foundry(self,foundry:str):
        db=self._db();now=time.time_ns();done=db.execute("SELECT COUNT(*) FROM work WHERE foundry=? AND state IN ('PASS','DEPLOYED','QUALIFIED')",(foundry,)).fetchone()[0];cur=db.execute("SELECT work_module_id FROM work WHERE foundry=? ORDER BY updated_ns DESC LIMIT 1",(foundry,)).fetchone();body={"foundry":foundry,"completed_count":done,"current_work_module":cur[0] if cur else None};sr=sha(body);db.execute("INSERT OR REPLACE INTO continuation VALUES(?,?,?,?,?)",(foundry,body["current_work_module"],done,sr,now));db.commit();db.close();return {**body,"state_root":sr}
