from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib, json, sqlite3, time, uuid

def canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha(v: Any) -> str:
    raw = v if isinstance(v, bytes) else canon(v).encode()
    return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class ServiceRequest:
    request_id: str
    service: str
    function: str
    customer_id: str
    payload: Dict[str, Any]
    authority_scope: str
    created_ns: int

class ReceiptLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS receipts(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id TEXT NOT NULL,
          service TEXT NOT NULL,
          function TEXT NOT NULL,
          status TEXT NOT NULL,
          result_json TEXT NOT NULL,
          result_hash TEXT NOT NULL,
          created_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_state(
          agent_id TEXT PRIMARY KEY,
          scope TEXT NOT NULL,
          epoch INTEGER NOT NULL,
          status TEXT NOT NULL,
          updated_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS run_state(
          run_id TEXT PRIMARY KEY,
          state_json TEXT NOT NULL,
          state_hash TEXT NOT NULL,
          updated_ns INTEGER NOT NULL
        );
        """)
        self.db.commit()

    def receipt(self, req: ServiceRequest, status: str, result: Dict[str, Any]) -> Dict[str, Any]:
        dg = sha(result)
        cur = self.db.execute(
            "INSERT INTO receipts(request_id,service,function,status,result_json,result_hash,created_ns) VALUES(?,?,?,?,?,?,?)",
            (req.request_id, req.service, req.function, status, canon(result), dg, time.time_ns())
        )
        self.db.commit()
        return {
            "receipt_id": f"RCPT-{cur.lastrowid}",
            "request_id": req.request_id,
            "service": req.service,
            "function": req.function,
            "status": status,
            "result_hash": dg
        }

    def upsert_agent(self, agent_id: str, scope: str, epoch: int, status: str):
        self.db.execute(
            "INSERT OR REPLACE INTO agent_state VALUES(?,?,?,?,?)",
            (agent_id, scope, epoch, status, time.time_ns())
        )
        self.db.commit()

    def get_agent(self, agent_id: str):
        row = self.db.execute("SELECT agent_id,scope,epoch,status FROM agent_state WHERE agent_id=?", (agent_id,)).fetchone()
        return None if row is None else {"agent_id":row[0],"scope":row[1],"epoch":row[2],"status":row[3]}

    def save_run(self, run_id: str, state: Dict[str, Any]):
        dg = sha(state)
        self.db.execute("INSERT OR REPLACE INTO run_state VALUES(?,?,?,?)", (run_id, canon(state), dg, time.time_ns()))
        self.db.commit()
        return dg

    def load_run(self, run_id: str):
        row = self.db.execute("SELECT state_json,state_hash FROM run_state WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        return {"state":json.loads(row[0]),"state_hash":row[1]}

class MarketServiceBroker:
    HR_GROUPS = ("research","runtime","verification","evolution","proof")

    def __init__(self, ledger_path: str | Path):
        self.ledger = ReceiptLedger(ledger_path)

    def _request(self, service, function, payload, customer_id="customer://local", authority_scope="SERVICE"):
        return ServiceRequest(
            request_id="REQ-"+uuid.uuid4().hex[:16],
            service=service,function=function,customer_id=customer_id,
            payload=payload,authority_scope=authority_scope,created_ns=time.time_ns()
        )

    def execute(self, service: str, function: str, payload: Dict[str, Any], *, customer_id="customer://local", authority_scope="SERVICE"):
        req = self._request(service,function,payload,customer_id,authority_scope)
        handler = getattr(self, f"_fn_{service}_{function}", None)
        if handler is None:
            result={"reason":"UNKNOWN_FUNCTION","service":service,"function":function}
            return {**self.ledger.receipt(req,"REJECTED",result),"result":result}
        try:
            result=handler(req)
            status=result.pop("_status","PASS")
        except Exception as exc:
            result={"error":type(exc).__name__,"detail":str(exc)}
            status="FAIL"
        return {
            **self.ledger.receipt(req,status,result),
            "hr_groups":list(self.HR_GROUPS),
            "result":result
        }

    def _fn_agent_control_register_agent(self, req):
        p=req.payload
        agent_id=p["agent_id"];scope=p["scope"]
        current=self.ledger.get_agent(agent_id)
        epoch=(current["epoch"]+1) if current else 1
        self.ledger.upsert_agent(agent_id,scope,epoch,"ACTIVE")
        return {"agent_id":agent_id,"scope":scope,"epoch":epoch,"state":"ACTIVE"}

    def _fn_agent_control_authorize_action(self, req):
        p=req.payload
        state=self.ledger.get_agent(p["agent_id"])
        if not state:
            return {"_status":"REJECTED","reason":"UNKNOWN_AGENT"}
        if state["status"]!="ACTIVE":
            return {"_status":"REJECTED","reason":"AGENT_NOT_ACTIVE","state":state}
        if p.get("expected_epoch") is not None and int(p["expected_epoch"])!=state["epoch"]:
            return {"_status":"REJECTED","reason":"STALE_EPOCH","state":state}
        allowed = p["required_scope"] == state["scope"] or state["scope"] == "ALL"
        return {"_status":"PASS" if allowed else "REJECTED","decision":"ALLOW" if allowed else "DENY",
                "agent_id":p["agent_id"],"epoch":state["epoch"],"scope":state["scope"]}

    def _fn_agent_control_fence_agent(self, req):
        p=req.payload
        state=self.ledger.get_agent(p["agent_id"])
        if not state:
            return {"_status":"REJECTED","reason":"UNKNOWN_AGENT"}
        epoch=state["epoch"]+1
        self.ledger.upsert_agent(p["agent_id"],state["scope"],epoch,"FENCED")
        return {"agent_id":p["agent_id"],"epoch":epoch,"state":"FENCED"}

    def _fn_runtime_supervisor_create_run(self, req):
        run_id=req.payload.get("run_id") or "RUN-"+uuid.uuid4().hex[:12]
        state={"run_id":run_id,"status":"RUNNING","step":0,"checkpoint":None,"continuation":"START"}
        dg=self.ledger.save_run(run_id,state)
        return {"run_id":run_id,"state_hash":dg,"state":state}

    def _fn_runtime_supervisor_checkpoint(self, req):
        p=req.payload
        current=self.ledger.load_run(p["run_id"])
        if not current:
            return {"_status":"REJECTED","reason":"UNKNOWN_RUN"}
        state=current["state"]
        state["step"]=int(p["step"])
        state["checkpoint"]=p["checkpoint"]
        state["continuation"]=p.get("continuation",f"RESUME_FROM_{p['step']}")
        dg=self.ledger.save_run(p["run_id"],state)
        return {"run_id":p["run_id"],"state_hash":dg,"continuation":state["continuation"]}

    def _fn_runtime_supervisor_rehydrate(self, req):
        current=self.ledger.load_run(req.payload["run_id"])
        if not current:
            return {"_status":"REJECTED","reason":"UNKNOWN_RUN"}
        return {"run_id":req.payload["run_id"],"rehydrated":True,**current}

    def _fn_handoff_guard_validate_handoff(self, req):
        p=req.payload
        required=set(p.get("required_fields",[]))
        supplied=set(p.get("payload",{}))
        missing=sorted(required-supplied)
        failures=[]
        if missing: failures.append("DATA_GAP")
        if p.get("expected_referent") and p.get("referent")!=p["expected_referent"]:
            failures.append("REFERENTIAL_DRIFT")
        if p.get("expected_digest") and sha(p.get("payload",{}))!=p["expected_digest"]:
            failures.append("SIGNAL_CORRUPTION")
        capabilities=set(p.get("recipient_capabilities",[]))
        needed=set(p.get("required_capabilities",[]))
        cap_gap=sorted(needed-capabilities)
        if cap_gap: failures.append("CAPABILITY_GAP")
        return {
            "_status":"PASS" if not failures else "REJECTED",
            "decision":"ALLOW" if not failures else "BLOCK",
            "failures":failures,
            "repair":{"missing_fields":missing,"missing_capabilities":cap_gap}
        }

    def _fn_proof_service_export_audit_pack(self, req):
        rows=self.ledger.db.execute(
            "SELECT request_id,service,function,status,result_hash,created_ns FROM receipts ORDER BY seq"
        ).fetchall()
        events=[
            {"request_id":r[0],"service":r[1],"function":r[2],"status":r[3],"result_hash":r[4],"created_ns":r[5]}
            for r in rows
        ]
        return {"event_count":len(events),"events":events,"audit_root":sha(events)}

    def _fn_ai_finops_measure_run(self, req):
        p=req.payload
        cost=float(p["cost"])
        successes=int(p["successful_tasks"])
        failures=int(p.get("failed_tasks",0))
        latency=float(p.get("p95_latency_ms",0))
        total=successes+failures
        return {
            "cost":cost,
            "successful_tasks":successes,
            "failed_tasks":failures,
            "success_rate":(successes/total if total else 0),
            "cost_per_success":(cost/successes if successes else None),
            "p95_latency_ms":latency,
            "economic_state":"MEASURED"
        }
