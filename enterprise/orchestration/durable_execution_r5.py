from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import hashlib, hmac, json, os, secrets, sqlite3, time

def canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()

def digest(v: Any) -> str:
    return hashlib.sha256(canon(v)).hexdigest()

class IntegrityError(RuntimeError): pass
class ReplayError(RuntimeError): pass
class StaleEpochError(RuntimeError): pass

class SignedEnvelopeAuthority:
    """HMAC-authenticated work-envelope authority with replay and epoch fencing."""
    def __init__(self, ledger_path: str | Path, key: bytes):
        if len(key) < 32: raise ValueError("key must be at least 32 bytes")
        self.ledger_path=Path(ledger_path); self.ledger_path.parent.mkdir(parents=True,exist_ok=True); self.key=key
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS consumed(nonce TEXT PRIMARY KEY, work_id TEXT NOT NULL, epoch INTEGER NOT NULL, consumed_ns INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS leases(work_id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, holder TEXT NOT NULL, updated_ns INTEGER NOT NULL)")
    def _db(self):
        db=sqlite3.connect(self.ledger_path,timeout=10); db.execute("PRAGMA busy_timeout=10000"); return db
    def sign(self,envelope:Dict[str,Any])->Dict[str,Any]:
        e=json.loads(json.dumps(envelope)); e.setdefault("nonce",secrets.token_hex(16)); e["signature_alg"]="HMAC-SHA256"
        payload={k:v for k,v in e.items() if k!="signature"}; e["signature"]=hmac.new(self.key,canon(payload),hashlib.sha256).hexdigest(); return e
    def verify(self,envelope:Dict[str,Any])->None:
        sig=envelope.get("signature",""); payload={k:v for k,v in envelope.items() if k!="signature"}; expected=hmac.new(self.key,canon(payload),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): raise IntegrityError("envelope signature mismatch")
    def consume_once(self,envelope:Dict[str,Any])->None:
        self.verify(envelope); work_id=envelope["work_id"]; epoch=int(envelope["continuation"]["epoch"]); nonce=envelope["nonce"]
        with self._db() as db:
            try: db.execute("INSERT INTO consumed VALUES(?,?,?,?)",(nonce,work_id,epoch,time.time_ns()))
            except sqlite3.IntegrityError as exc: raise ReplayError(nonce) from exc
    def acquire_lease(self,work_id:str,holder:str,requested_epoch:int|None=None)->int:
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE"); row=db.execute("SELECT epoch FROM leases WHERE work_id=?",(work_id,)).fetchone(); current=row[0] if row else 0; next_epoch=current+1
            if requested_epoch is not None and requested_epoch<=current:
                db.rollback(); raise StaleEpochError(f"requested {requested_epoch}, current {current}")
            if requested_epoch is not None: next_epoch=requested_epoch
            db.execute("INSERT INTO leases(work_id,epoch,holder,updated_ns) VALUES(?,?,?,?) ON CONFLICT(work_id) DO UPDATE SET epoch=excluded.epoch,holder=excluded.holder,updated_ns=excluded.updated_ns",(work_id,next_epoch,holder,time.time_ns())); db.commit(); return next_epoch
    def current_lease(self,work_id:str):
        with self._db() as db: return db.execute("SELECT epoch,holder FROM leases WHERE work_id=?",(work_id,)).fetchone()

class DomainAuthorityAtomicCoordinator:
    """Local crash-atomic transaction spanning Foundry domain state + DA authority state via SQLite ATTACH."""
    def __init__(self,control_db:str|Path,authority_db:str|Path):
        self.control_db=Path(control_db); self.authority_db=Path(authority_db); self.control_db.parent.mkdir(parents=True,exist_ok=True); self.authority_db.parent.mkdir(parents=True,exist_ok=True); self._ensure_schema()
    def _connect(self):
        db=sqlite3.connect(self.control_db,timeout=20,isolation_level=None); db.execute("PRAGMA busy_timeout=20000"); db.execute("PRAGMA journal_mode=DELETE"); db.execute("ATTACH DATABASE ? AS authority",(str(self.authority_db),)); return db
    def _ensure_schema(self):
        db=sqlite3.connect(self.control_db); db.execute("CREATE TABLE IF NOT EXISTS domains(id TEXT PRIMARY KEY,domain TEXT UNIQUE,registrar TEXT,state TEXT,owner_scope TEXT,renewal_at TEXT)"); db.execute("CREATE TABLE IF NOT EXISTS tx_journal(tx_id TEXT PRIMARY KEY, domain TEXT NOT NULL, state TEXT NOT NULL, created_ns INTEGER NOT NULL, committed_ns INTEGER)"); db.commit(); db.close()
        adb=sqlite3.connect(self.authority_db); adb.execute("CREATE TABLE IF NOT EXISTS zones(zone TEXT PRIMARY KEY, primary_ns TEXT NOT NULL, admin_rname TEXT NOT NULL, serial INTEGER NOT NULL, owner_scope TEXT NOT NULL, status TEXT NOT NULL)"); adb.execute("CREATE TABLE IF NOT EXISTS zone_records(zone TEXT NOT NULL,name TEXT NOT NULL,rrtype TEXT NOT NULL,value TEXT NOT NULL,ttl INTEGER NOT NULL,status TEXT NOT NULL,PRIMARY KEY(zone,name,rrtype,value))"); adb.commit(); adb.close()
    def provision(self,tx_id:str,domain:str,owner_scope:str,ip:str,failpoint:str|None=None):
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE"); db.execute("INSERT INTO tx_journal VALUES(?,?,?,?,NULL)",(tx_id,domain,"STARTED",time.time_ns())); db.execute("INSERT INTO domains VALUES(?,?,?,?,?,NULL)",("DOM-"+digest(tx_id)[:12],domain,"KEDDEH_INTERNAL","BOUND_AUTHORITATIVE",owner_scope))
            if failpoint=="after_control": raise RuntimeError("injected crash after control write")
            serial=int(time.strftime("%Y%m%d01",time.gmtime())); db.execute("INSERT INTO authority.zones VALUES(?,?,?,?,?,?)",(domain,"ns1."+domain,"hostmaster."+domain,serial,owner_scope,"ACTIVE")); db.execute("INSERT INTO authority.zone_records VALUES(?,?,?,?,?,?)",(domain,domain,"A",ip,300,"ACTIVE"))
            if failpoint=="after_authority": raise RuntimeError("injected crash after authority write")
            db.execute("UPDATE tx_journal SET state='COMMITTED', committed_ns=? WHERE tx_id=?",(time.time_ns(),tx_id)); db.commit(); return {"tx_id":tx_id,"domain":domain,"state":"COMMITTED"}
        except Exception:
            db.rollback(); raise
        finally: db.close()
    def observe(self,domain:str):
        c=sqlite3.connect(self.control_db); control=c.execute("SELECT domain,state,owner_scope FROM domains WHERE domain=?",(domain,)).fetchone(); c.close(); a=sqlite3.connect(self.authority_db); zone=a.execute("SELECT zone,status,owner_scope FROM zones WHERE zone=?",(domain,)).fetchone(); rec=a.execute("SELECT name,rrtype,value,ttl,status FROM zone_records WHERE zone=?",(domain,)).fetchall(); a.close(); return {"control":control,"zone":zone,"records":rec}

class CheckpointStore:
    """Signed logical checkpoint for agent/process replacement."""
    def __init__(self,path:str|Path,key:bytes): self.path=Path(path); self.key=key
    def write(self,state:Dict[str,Any]):
        payload=json.loads(json.dumps(state)); payload["checkpoint_ns"]=time.time_ns(); sig=hmac.new(self.key,canon(payload),hashlib.sha256).hexdigest(); wrapper={"payload":payload,"signature":sig}; tmp=self.path.with_suffix(self.path.suffix+".tmp"); tmp.write_text(json.dumps(wrapper,indent=2)); os.replace(tmp,self.path); return digest(wrapper)
    def read(self):
        wrapper=json.loads(self.path.read_text()); expected=hmac.new(self.key,canon(wrapper["payload"]),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,wrapper["signature"]): raise IntegrityError("checkpoint signature mismatch")
        return wrapper["payload"]
