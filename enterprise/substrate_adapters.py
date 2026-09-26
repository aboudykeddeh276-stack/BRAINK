from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Protocol
import fcntl, hashlib, json, sqlite3, os

def _bytes(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def digest(v): return hashlib.sha256(v if isinstance(v,bytes) else _bytes(v)).hexdigest()
class Adapter(Protocol):
    adapter_id:str; schemes:tuple[str,...]; capabilities:tuple[str,...]
    def probe(self,backing:str)->Dict[str,Any]: ...
    def apply(self,backing:str,logical:str,operation:str,payload:Any=None)->Dict[str,Any]: ...
@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id:str; schemes:tuple[str,...]; capabilities:tuple[str,...]; priority:int; health:str='UNKNOWN'
class FileJsonAdapter:
    adapter_id='adapter://file/json'; schemes=('file://',); capabilities=('READ','WRITE','CAS_WRITE','PROBE','ATOMIC','DURABLE','SERIALIZED_WRITE')
    def probe(self,backing):
        p=Path(backing.removeprefix('file://')); return {'status':'READY','exists':p.exists(),'parent_exists':p.parent.exists()}
    def _commit(self,p,raw):
        tmp=p.with_suffix(p.suffix+'.tmp')
        try:
            with tmp.open('wb') as fh:
                fh.write(raw); fh.flush(); os.fsync(fh.fileno())
            os.replace(tmp,p)
            fd=os.open(p.parent,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        finally:
            if tmp.exists(): tmp.unlink()
    def apply(self,backing,logical,operation,payload=None):
        p=Path(backing.removeprefix('file://')); p.parent.mkdir(parents=True,exist_ok=True)
        lock_path=p.with_name(p.name+'.lock'); lock_path.touch(exist_ok=True)
        if operation in {'WRITE','CAS_WRITE'}:
            if operation=='CAS_WRITE':
                if not isinstance(payload,dict) or 'value' not in payload or 'expected_hash' not in payload:
                    return {'status':'INVALID_CAS_PAYLOAD'}
                expected=payload['expected_hash']; value=payload['value']
            else:
                expected=None; value=payload
            raw=_bytes(value)
            with lock_path.open('r+') as lock_fh:
                fcntl.flock(lock_fh.fileno(),fcntl.LOCK_EX)
                try:
                    current_hash=None
                    if p.exists():
                        current=json.loads(p.read_text()); current_hash=digest(current)
                    if operation=='CAS_WRITE' and current_hash!=expected:
                        return {'status':'CONFLICT','expected_hash':expected,'current_hash':current_hash,'path':str(p)}
                    self._commit(p,raw)
                finally:
                    fcntl.flock(lock_fh.fileno(),fcntl.LOCK_UN)
            return {'status':'COMMITTED','value_hash':hashlib.sha256(raw).hexdigest(),'path':str(p),'durability':'FILE_AND_DIRECTORY_FSYNC','serialization':'FLOCK_EX','compare_and_swap':operation=='CAS_WRITE'}
        if operation=='READ':
            with lock_path.open('r+') as lock_fh:
                fcntl.flock(lock_fh.fileno(),fcntl.LOCK_SH)
                try:
                    if not p.exists(): return {'status':'HOLE','path':str(p)}
                    v=json.loads(p.read_text()); return {'status':'READ','value':v,'value_hash':digest(v)}
                finally: fcntl.flock(lock_fh.fileno(),fcntl.LOCK_UN)
        return {'status':'UNSUPPORTED_OPERATION','operation':operation}
class SQLiteJsonAdapter:
    adapter_id='adapter://sqlite/json'; schemes=('sqlite://',); capabilities=('READ','WRITE','PROBE','ATOMIC')
    def _parts(self,backing):
        spec=backing.removeprefix('sqlite://'); path,_,table=spec.partition('#'); return Path(path),table or 'objects'
    def _conn(self,backing):
        path,table=self._parts(backing); path.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(path); c.execute(f'CREATE TABLE IF NOT EXISTS {table}(logical TEXT PRIMARY KEY,payload TEXT NOT NULL,value_hash TEXT NOT NULL)'); return c,table
    def probe(self,backing): c,t=self._conn(backing); c.close(); return {'status':'READY','table':t}
    def apply(self,backing,logical,operation,payload=None):
        c,t=self._conn(backing)
        try:
            if operation=='WRITE':
                raw=json.dumps(payload,sort_keys=True,separators=(',',':')); h=hashlib.sha256(raw.encode()).hexdigest(); c.execute(f'INSERT OR REPLACE INTO {t} VALUES(?,?,?)',(logical,raw,h)); c.commit(); return {'status':'COMMITTED','value_hash':h,'table':t}
            if operation=='READ':
                r=c.execute(f'SELECT payload,value_hash FROM {t} WHERE logical=?',(logical,)).fetchone(); return {'status':'HOLE'} if not r else {'status':'READ','value':json.loads(r[0]),'value_hash':r[1]}
            return {'status':'UNSUPPORTED_OPERATION','operation':operation}
        finally:c.close()
class MemoryAdapter:
    adapter_id='adapter://memory/json'; schemes=('mem://',); capabilities=('READ','WRITE','PROBE')
    def __init__(self):self.data={}
    def probe(self,backing):return {'status':'READY','objects':len(self.data)}
    def apply(self,backing,logical,operation,payload=None):
        k=(backing,logical)
        if operation=='WRITE':self.data[k]=payload;return {'status':'COMMITTED','value_hash':digest(payload)}
        if operation=='READ':return {'status':'HOLE'} if k not in self.data else {'status':'READ','value':self.data[k],'value_hash':digest(self.data[k])}
        return {'status':'UNSUPPORTED_OPERATION'}
class CapabilityRegistry:
    def __init__(self):self.adapters={};self.descriptors={}
    def register(self,adapter,priority=100):self.adapters[adapter.adapter_id]=adapter;self.descriptors[adapter.adapter_id]=AdapterDescriptor(adapter.adapter_id,adapter.schemes,adapter.capabilities,priority)
    def discover(self,backing,operation):
        candidates=[]
        for aid,d in self.descriptors.items():
            if operation not in d.capabilities or not any(backing.startswith(s) for s in d.schemes):continue
            probe=self.adapters[aid].probe(backing)
            if probe.get('status')=='READY':candidates.append((d.priority,aid,probe))
        if not candidates:return {'status':'NO_ADAPTER','backing':backing,'operation':operation}
        _,aid,probe=sorted(candidates,key=lambda x:(x[0],x[1]))[0];return {'status':'RESOLVED','adapter_id':aid,'probe':probe}
    def invoke(self,adapter_id,**kwargs):return self.adapters[adapter_id].apply(**kwargs)
