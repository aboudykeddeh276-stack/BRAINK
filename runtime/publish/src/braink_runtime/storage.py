from __future__ import annotations
import json, os, sqlite3, threading
from pathlib import Path
from typing import Any

class Store:
    def __init__(self, root: str):
        self.root=Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.db=self.root/'runtime.sqlite3'; self.ledger=self.root/'proof-ledger.jsonl'
        self.lock=threading.RLock(); self._init()
    def _conn(self): return sqlite3.connect(self.db)
    def _init(self):
        with self._conn() as c:
            c.execute('CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT NOT NULL, version INTEGER NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS objects (object_id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, receipt TEXT NOT NULL)')
    def get_state(self,k:str)->tuple[Any,int]:
        with self._conn() as c:
            r=c.execute('SELECT v,version FROM state WHERE k=?',(k,)).fetchone()
        return (json.loads(r[0]),r[1]) if r else ({},0)
    def put_state(self,k:str,v:Any,version:int):
        with self._conn() as c:
            c.execute('INSERT INTO state(k,v,version) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v,version=excluded.version',(k,json.dumps(v,sort_keys=True,separators=(',',':')),version))
    def put_object(self,object_id:str,body:dict):
        with self._conn() as c:
            c.execute('INSERT INTO objects(object_id,body) VALUES(?,?) ON CONFLICT(object_id) DO UPDATE SET body=excluded.body',(object_id,json.dumps(body,sort_keys=True)))
    def get_object(self,object_id:str):
        with self._conn() as c: r=c.execute('SELECT body FROM objects WHERE object_id=?',(object_id,)).fetchone()
        return json.loads(r[0]) if r else None
    def list_objects(self):
        with self._conn() as c: rs=c.execute('SELECT body FROM objects ORDER BY object_id').fetchall()
        return [json.loads(r[0]) for r in rs]
    def prior_receipt(self,request_id:str):
        with self._conn() as c: r=c.execute('SELECT receipt FROM requests WHERE request_id=?',(request_id,)).fetchone()
        return json.loads(r[0]) if r else None
    def save_receipt(self,request_id:str,receipt:dict):
        with self._conn() as c: c.execute('INSERT INTO requests(request_id,receipt) VALUES(?,?)',(request_id,json.dumps(receipt,sort_keys=True)))
    def append_ledger(self,event:dict)->int:
        with self.lock:
            idx=0
            if self.ledger.exists():
                with self.ledger.open('rb') as f: idx=sum(1 for _ in f)
            with self.ledger.open('a',encoding='utf-8') as f: f.write(json.dumps(event,sort_keys=True,separators=(',',':'))+'\n')
            return idx
    def read_ledger(self):
        if not self.ledger.exists(): return []
        return [json.loads(x) for x in self.ledger.read_text().splitlines() if x.strip()]
