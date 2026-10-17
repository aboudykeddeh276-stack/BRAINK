from __future__ import annotations
import hashlib, json, sqlite3, threading, time, uuid
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id TEXT PRIMARY KEY, product TEXT NOT NULL, display_name TEXT NOT NULL,
  state TEXT NOT NULL, created_at_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS identities (
  identity_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
  subject_ref TEXT NOT NULL, roles_json TEXT NOT NULL, state TEXT NOT NULL,
  created_at_ns INTEGER NOT NULL, UNIQUE(tenant_id, subject_ref)
);
CREATE TABLE IF NOT EXISTS entitlements (
  event_key TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
  provider TEXT NOT NULL, provider_reference TEXT NOT NULL, sku TEXT NOT NULL,
  amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0), currency TEXT NOT NULL,
  payment_state TEXT NOT NULL, entitlement_state TEXT NOT NULL,
  capability_unlock INTEGER NOT NULL CHECK(capability_unlock IN (0,1)), created_at_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
  service TEXT NOT NULL, payload_ref TEXT NOT NULL, state TEXT NOT NULL,
  created_at_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS receipts (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, subject TEXT NOT NULL,
  payload_hash TEXT NOT NULL, previous_hash TEXT NOT NULL, receipt_hash TEXT NOT NULL UNIQUE,
  observed_at_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS braink_evidence_sync (
  receipt_hash TEXT PRIMARY KEY REFERENCES receipts(receipt_hash),
  state TEXT NOT NULL,
  event_root TEXT,
  last_error TEXT,
  updated_at_ns INTEGER NOT NULL
);
"""

class ControlPlaneStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    @staticmethod
    def _canonical(value: Any) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    def _receipt(self, event: str, subject: str, payload: Any) -> dict[str, Any]:
        payload_hash = hashlib.sha256(self._canonical(payload)).hexdigest()
        last = self.conn.execute("SELECT receipt_hash FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
        previous = last[0] if last else "0" * 64
        observed = time.time_ns()
        next_seq = self.conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM receipts").fetchone()[0]
        body = {"seq":next_seq,"event":event,"subject":subject,"payload_hash":payload_hash,"previous_hash":previous,"observed_at_ns":observed}
        receipt_hash = hashlib.sha256(self._canonical(body)).hexdigest()
        self.conn.execute("INSERT INTO receipts(seq,event,subject,payload_hash,previous_hash,receipt_hash,observed_at_ns) VALUES(?,?,?,?,?,?,?)", (next_seq,event,subject,payload_hash,previous,receipt_hash,observed))
        self.conn.execute(
            "INSERT OR IGNORE INTO braink_evidence_sync(receipt_hash,state,event_root,last_error,updated_at_ns) VALUES(?,?,?,?,?)",
            (receipt_hash,"PENDING",None,None,time.time_ns()),
        )
        return {**body,"receipt_hash":receipt_hash}

    def mark_braink_evidence_synced(self, receipt_hash: str, event_root: str) -> dict[str, Any]:
        with self.lock:
            self.conn.execute(
                "UPDATE braink_evidence_sync SET state='SYNCED',event_root=?,last_error=NULL,updated_at_ns=? WHERE receipt_hash=?",
                (event_root,time.time_ns(),receipt_hash),
            )
            row=self.conn.execute("SELECT * FROM braink_evidence_sync WHERE receipt_hash=?",(receipt_hash,)).fetchone()
            if not row: raise KeyError("LOCAL_RECEIPT_NOT_FOUND")
            return dict(row)

    def mark_braink_evidence_failed(self, receipt_hash: str, error: str) -> dict[str, Any]:
        with self.lock:
            self.conn.execute(
                "UPDATE braink_evidence_sync SET state='FAILED',last_error=?,updated_at_ns=? WHERE receipt_hash=?",
                (error,time.time_ns(),receipt_hash),
            )
            row=self.conn.execute("SELECT * FROM braink_evidence_sync WHERE receipt_hash=?",(receipt_hash,)).fetchone()
            if not row: raise KeyError("LOCAL_RECEIPT_NOT_FOUND")
            return dict(row)

    def pending_braink_evidence(self) -> list[dict[str, Any]]:
        rows=self.conn.execute(
            """SELECT r.*,s.state AS braink_state,s.event_root,s.last_error,s.updated_at_ns AS braink_updated_at_ns
               FROM receipts r JOIN braink_evidence_sync s ON s.receipt_hash=r.receipt_hash
               WHERE s.state!='SYNCED' ORDER BY r.seq"""
        ).fetchall()
        return [dict(r) for r in rows]

    def create_tenant(self, product: str, display_name: str) -> tuple[dict, dict]:
        with self.lock:
            tid=f"tenant_{uuid.uuid4().hex}"; now=time.time_ns()
            row={"tenant_id":tid,"product":product,"display_name":display_name,"state":"ACTIVE","created_at_ns":now}
            self.conn.execute("INSERT INTO tenants VALUES(?,?,?,?,?)", tuple(row.values()))
            return row, self._receipt("TENANT_CREATED", tid, row)

    def register_identity(self, tenant_id: str, subject_ref: str, roles: list[str]) -> tuple[dict, dict]:
        with self.lock:
            self._require_tenant(tenant_id)
            existing=self.conn.execute("SELECT * FROM identities WHERE tenant_id=? AND subject_ref=?",(tenant_id,subject_ref)).fetchone()
            if existing:
                row=self._identity(existing)
                return row, self._receipt("IDENTITY_IDEMPOTENT_REPLAY", row["identity_id"], row)
            iid=f"identity_{uuid.uuid4().hex}"; now=time.time_ns(); roles=sorted(set(roles))
            row={"identity_id":iid,"tenant_id":tenant_id,"subject_ref":subject_ref,"roles":roles,"state":"ACTIVE","created_at_ns":now}
            self.conn.execute("INSERT INTO identities VALUES(?,?,?,?,?,?)",(iid,tenant_id,subject_ref,json.dumps(roles),"ACTIVE",now))
            return row, self._receipt("IDENTITY_REGISTERED", iid, row)

    def apply_payment_event(self, **event: Any) -> tuple[dict, dict]:
        with self.lock:
            self._require_tenant(event["tenant_id"])
            key=f'{event["provider"]}:{event["provider_reference"]}'
            existing=self.conn.execute("SELECT * FROM entitlements WHERE event_key=?",(key,)).fetchone()
            if existing:
                row=self._entitlement(existing)
                return row, self._receipt("PAYMENT_EVENT_IDEMPOTENT_REPLAY", key, row)
            allowed=event["terminal_state"] in {"CAPTURED","SETTLED","SUCCEEDED"}; now=time.time_ns()
            row={"event_key":key,"tenant_id":event["tenant_id"],"provider":event["provider"],"provider_reference":event["provider_reference"],"sku":event["sku"],"amount_minor":event["amount_minor"],"currency":event["currency"],"payment_state":event["terminal_state"],"entitlement_state":"ACTIVE" if allowed else "INACTIVE","capability_unlock":bool(allowed),"created_at_ns":now}
            self.conn.execute("INSERT INTO entitlements VALUES(?,?,?,?,?,?,?,?,?,?,?)",(key,row["tenant_id"],row["provider"],row["provider_reference"],row["sku"],row["amount_minor"],row["currency"],row["payment_state"],row["entitlement_state"],int(row["capability_unlock"]),now))
            return row, self._receipt("PAYMENT_EVENT_APPLIED", key, row)

    def enqueue_job(self, tenant_id: str, service: str, payload_ref: str) -> tuple[dict, dict]:
        with self.lock:
            self._require_tenant(tenant_id); jid=f"job_{uuid.uuid4().hex}"; now=time.time_ns()
            row={"job_id":jid,"tenant_id":tenant_id,"service":service,"payload_ref":payload_ref,"state":"QUEUED","created_at_ns":now}
            self.conn.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?)",tuple(row.values()))
            return row, self._receipt("JOB_QUEUED", jid, row)

    def _require_tenant(self, tenant_id: str) -> None:
        if not self.conn.execute("SELECT 1 FROM tenants WHERE tenant_id=?",(tenant_id,)).fetchone(): raise KeyError("TENANT_NOT_FOUND")

    @staticmethod
    def _identity(r: sqlite3.Row) -> dict: return {"identity_id":r["identity_id"],"tenant_id":r["tenant_id"],"subject_ref":r["subject_ref"],"roles":json.loads(r["roles_json"]),"state":r["state"],"created_at_ns":r["created_at_ns"]}
    @staticmethod
    def _entitlement(r: sqlite3.Row) -> dict:
        d=dict(r); d["capability_unlock"]=bool(d["capability_unlock"]); return d

    def verify_chain(self) -> bool:
        previous="0"*64
        for r in self.conn.execute("SELECT * FROM receipts ORDER BY seq"):
            body={"seq":r["seq"],"event":r["event"],"subject":r["subject"],"payload_hash":r["payload_hash"],"previous_hash":r["previous_hash"],"observed_at_ns":r["observed_at_ns"]}
            if r["previous_hash"] != previous or hashlib.sha256(self._canonical(body)).hexdigest()!=r["receipt_hash"]: return False
            previous=r["receipt_hash"]
        return True

    def snapshot(self) -> dict[str, Any]:
        sync_counts={r["state"]:r["count"] for r in self.conn.execute("SELECT state,COUNT(*) AS count FROM braink_evidence_sync GROUP BY state")}
        return {
          "counts": {"tenants":self.conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0],"identities":self.conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0],"entitlements":self.conn.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0],"jobs":self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],"receipts":self.conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]},
          "receipts":[dict(r) for r in self.conn.execute("SELECT * FROM receipts ORDER BY seq")],
          "chain_valid":self.verify_chain(),
          "braink_evidence_sync_counts":sync_counts,
          "braink_evidence_pending":self.pending_braink_evidence(),
        }