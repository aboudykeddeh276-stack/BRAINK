from __future__ import annotations
import json, sqlite3, time, hashlib
from pathlib import Path

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"))
def sha(v): return hashlib.sha256(canon(v).encode()).hexdigest()

class CapabilityRegistry:
    def __init__(self,path):
        self.path=Path(path)
        self.db=sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS adapters(
          adapter_id TEXT PRIMARY KEY,status TEXT NOT NULL,binding TEXT,evidence_root TEXT,updated_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS obligations(
          obligation_id TEXT PRIMARY KEY,sector TEXT NOT NULL,function TEXT NOT NULL,adapter_id TEXT NOT NULL,
          state TEXT NOT NULL,priority INTEGER NOT NULL,work_module_id TEXT NOT NULL,created_ns INTEGER NOT NULL,updated_ns INTEGER NOT NULL
        );
        """)
        self.db.commit()
    def register_adapter(self,adapter_id,status="BOUND",binding=None,evidence=None):
        self.db.execute("INSERT OR REPLACE INTO adapters VALUES(?,?,?,?,?)",(adapter_id,status,binding,sha(evidence or {}),time.time_ns()));self.db.commit()
    def adapter(self,adapter_id):
        r=self.db.execute("SELECT adapter_id,status,binding,evidence_root FROM adapters WHERE adapter_id=?",(adapter_id,)).fetchone()
        return None if r is None else {"adapter_id":r[0],"status":r[1],"binding":r[2],"evidence_root":r[3]}
    def ensure_obligation(self,sector,function,adapter_id,priority=50):
        key=sha({"sector":sector,"function":function,"adapter":adapter_id})[:20];oid="OBL-"+key;wm="WM-CAPABILITY-"+key;now=time.time_ns()
        self.db.execute("INSERT OR IGNORE INTO obligations VALUES(?,?,?,?,?,?,?,?,?)",(oid,sector,function,adapter_id,"OPEN",priority,wm,now,now));self.db.commit();return self.get_obligation(oid)
    def get_obligation(self,oid):
        r=self.db.execute("SELECT obligation_id,sector,function,adapter_id,state,priority,work_module_id,created_ns,updated_ns FROM obligations WHERE obligation_id=?",(oid,)).fetchone()
        return None if r is None else {"obligation_id":r[0],"sector":r[1],"function":r[2],"adapter_id":r[3],"state":r[4],"priority":r[5],"work_module_id":r[6],"created_ns":r[7],"updated_ns":r[8]}
    def open_obligations(self):
        rows=self.db.execute("SELECT obligation_id,sector,function,adapter_id,state,priority,work_module_id FROM obligations WHERE state='OPEN' ORDER BY priority DESC, obligation_id").fetchall()
        return [{"obligation_id":r[0],"sector":r[1],"function":r[2],"adapter_id":r[3],"state":r[4],"priority":r[5],"work_module_id":r[6]} for r in rows]
