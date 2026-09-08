from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import hashlib
import json
import sqlite3
import subprocess
import threading
import time

from enterprise.orchestration.cross_sector_executor import CrossSectorExecutor
from enterprise.orchestration.durable_execution_r5 import SignedEnvelopeAuthority
from enterprise.runtime.process_supervisor import ManagedProcess
from runtime.runtime_registry import RuntimeRegistry
from runtime.runtime_route_registry import RuntimeRouteRegistry

SCHEMA = "braink.resident-execution-envelope.v1"
FABRIC_ID = "braink://local/execution-fabric"
ALLOWED_OPERATIONS = {"DESCRIBE_ROUTE", "RUN_ONCE", "START_RUNTIME", "STOP_RUNTIME", "RESTART_RUNTIME", "READBACK_RUNTIME"}
TERMINAL_STATES = {"COMPLETED", "FAILED", "REJECTED"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class AdmissionError(RuntimeError):
    pass


class RoutePolicyError(RuntimeError):
    pass


class ExecutionJournal:
    """Crash-durable work/event journal. It records observed transitions, never inferred success."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS work(
                    work_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    route TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    actor_json TEXT NOT NULL,
                    envelope_root TEXT NOT NULL,
                    result_json TEXT,
                    proof_root TEXT,
                    failure TEXT,
                    updated_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    event_root TEXT NOT NULL,
                    created_ns INTEGER NOT NULL
                );
                """
            )

    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def transition(self, envelope: Dict[str, Any], state: str, payload: Dict[str, Any] | None = None) -> dict:
        payload = payload or {}
        now = time.time_ns()
        work_id = envelope["work_id"]
        material = {
            "work_id": work_id,
            "state": state,
            "epoch": int(envelope["continuation"]["epoch"]),
            "route": envelope["route"],
            "operation": envelope["operation"],
            "payload": payload,
            "created_ns": now,
        }
        event_root = root(material)
        result = payload.get("result")
        proof_root = payload.get("proof_root")
        failure = payload.get("failure")
        with self._db() as db:
            current = db.execute("SELECT state FROM work WHERE work_id=?", (work_id,)).fetchone()
            if current and current["state"] in TERMINAL_STATES and state not in TERMINAL_STATES:
                raise AdmissionError(f"terminal work cannot transition: {work_id}:{current['state']}->{state}")
            db.execute(
                """INSERT INTO work(work_id,state,epoch,route,operation,actor_json,envelope_root,result_json,proof_root,failure,updated_ns)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(work_id) DO UPDATE SET
                     state=excluded.state, epoch=excluded.epoch, result_json=excluded.result_json,
                     proof_root=excluded.proof_root, failure=excluded.failure, updated_ns=excluded.updated_ns""",
                (
                    work_id, state, int(envelope["continuation"]["epoch"]), envelope["route"], envelope["operation"],
                    canonical(envelope["actor"]).decode(), envelope["envelope_root"],
                    canonical(result).decode() if result is not None else None, proof_root, failure, now,
                ),
            )
            db.execute(
                "INSERT INTO events(work_id,state,payload_json,event_root,created_ns) VALUES(?,?,?,?,?)",
                (work_id, state, canonical(payload).decode(), event_root, now),
            )
            db.commit()
        return {"work_id": work_id, "state": state, "event_root": event_root, "created_ns": now}

    def get(self, work_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM work WHERE work_id=?", (work_id,)).fetchone()
            if not row:
                return None
            out = dict(row)
            out["actor"] = json.loads(out.pop("actor_json"))
            out["result"] = json.loads(out.pop("result_json")) if out.get("result_json") else None
            return out

    def events(self, work_id: str) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM events WHERE work_id=? ORDER BY seq", (work_id,)).fetchall()
            return [dict(r) for r in rows]


@dataclass
class ExecutionPolicy:
    max_run_seconds: float = 120.0
    require_proof: bool = True


class ResidentExecutionFabric:
    """Resident execution convergence layer.

    GitHub, web, admin and agent surfaces are ingress carriers. This object owns admission of
    authenticated work into resident mechanics, but it does not invent arbitrary shell execution.
    Commands are resolved only from RuntimeRouteRegistry.
    """

    def __init__(
        self,
        repo_root: str | Path,
        state_dir: str | Path,
        authority_key: bytes,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.policy = policy or ExecutionPolicy()
        self.routes = RuntimeRouteRegistry(self.repo_root)
        self.registry = RuntimeRegistry(self.state_dir / "runtime-registry.sqlite3")
        self.authority = SignedEnvelopeAuthority(self.state_dir / "admission.sqlite3", authority_key)
        self.journal = ExecutionJournal(self.state_dir / "execution-journal.sqlite3")
        self.executor = CrossSectorExecutor()
        self.executor.bind("runtime", "runtime/runtime_route_registry.py+enterprise/runtime/process_supervisor.py", self._runtime_handler, "BRAINK")
        self._processes: dict[str, ManagedProcess] = {}
        self._lock = threading.RLock()

    def available_routes(self) -> list[str]:
        return self.routes.routes()

    def sign(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Sign an already-authorized internal envelope. External carriers should not receive this key."""
        prepared = json.loads(json.dumps(envelope))
        prepared.setdefault("schema", SCHEMA)
        prepared.setdefault("sector", "runtime")
        prepared.setdefault("proof_required", True)
        prepared.setdefault("authority", "braink://local/orchestrator")
        prepared.setdefault("continuation", {"epoch": 1, "status": "ADMITTED"})
        prepared["envelope_root"] = root({k: v for k, v in prepared.items() if k not in {"signature", "envelope_root"}})
        return self.authority.sign(prepared)

    def _validate(self, envelope: Dict[str, Any]) -> None:
        required = ("schema", "work_id", "actor", "sector", "route", "operation", "continuation", "envelope_root")
        missing = [k for k in required if k not in envelope]
        if missing:
            raise AdmissionError("missing fields: " + ",".join(missing))
        if envelope["schema"] != SCHEMA:
            raise AdmissionError("invalid schema")
        if envelope["sector"] != "runtime":
            raise AdmissionError("unbound sector")
        if envelope["operation"] not in ALLOWED_OPERATIONS:
            raise AdmissionError("unsupported operation")
        if envelope["route"] not in self.available_routes():
            raise RoutePolicyError("route is not registered: " + str(envelope["route"]))
        epoch = envelope.get("continuation", {}).get("epoch")
        if not isinstance(epoch, int) or epoch < 1:
            raise AdmissionError("continuation epoch must be positive integer")
        expected = root({k: v for k, v in envelope.items() if k not in {"signature", "envelope_root", "nonce", "signature_alg"}})
        if envelope["envelope_root"] != expected:
            raise AdmissionError("envelope root mismatch")
        if not isinstance(envelope["actor"], dict) or not envelope["actor"].get("type"):
            raise AdmissionError("actor.type required")

    def dispatch(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        self._validate(envelope)
        self.authority.consume_once(envelope)
        epoch = int(envelope["continuation"]["epoch"])
        self.authority.acquire_lease(envelope["work_id"], FABRIC_ID, requested_epoch=epoch)
        self.journal.transition(envelope, "ADMITTED", {"carrier": envelope.get("carrier"), "route": envelope["route"]})
        self.journal.transition(envelope, "EXECUTING", {})
        try:
            execution = self.executor.execute("runtime", envelope)
            if execution.get("state") != "READ_BACK":
                raise RuntimeError("runtime sector did not return readback")
            receipt = execution["receipt"]
            proof_root = receipt["receipt_root"]
            if self.policy.require_proof and not proof_root:
                raise RuntimeError("completion without proof")
            result = {
                "status": "COMPLETED",
                "work_id": envelope["work_id"],
                "correlation_id": envelope.get("correlation_id"),
                "route": envelope["route"],
                "operation": envelope["operation"],
                "observed": receipt["observed"],
                "proof": proof_root,
                "continuation": execution["envelope"]["continuation"],
                "envelope_root": execution["envelope"]["envelope_root"],
            }
            self.journal.transition(envelope, "COMPLETED", {"result": result, "proof_root": proof_root})
            return result
        except Exception as exc:
            self.journal.transition(envelope, "FAILED", {"failure": f"{type(exc).__name__}:{exc}"})
            raise

    def _route(self, route: str) -> dict:
        spec = self.routes.resolve(route)
        argv = list(spec.get("argv") or [])
        if not argv or not all(isinstance(x, str) and x for x in argv):
            raise RoutePolicyError("registered route has invalid argv")
        return spec

    def _runtime_handler(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        operation = envelope["operation"]
        spec = self._route(envelope["route"])
        if operation == "DESCRIBE_ROUTE":
            return {"state": "BOUND", "route": envelope["route"], "runtime": spec}
        if operation == "RUN_ONCE":
            return self._run_once(spec)
        if operation == "START_RUNTIME":
            return self._start_runtime(spec)
        if operation == "STOP_RUNTIME":
            return self._stop_runtime(spec)
        if operation == "RESTART_RUNTIME":
            self._stop_runtime(spec)
            return self._start_runtime(spec, restarted=True)
        if operation == "READBACK_RUNTIME":
            return self._readback_runtime(spec)
        raise AdmissionError("unreachable operation")

    def _run_once(self, spec: dict) -> Dict[str, Any]:
        started = time.monotonic_ns()
        p = subprocess.run(
            spec["argv"], cwd=self.repo_root, capture_output=True, text=True,
            timeout=self.policy.max_run_seconds, shell=False,
        )
        observed = {
            "runtime_id": spec["runtime_id"], "runtime_class": spec["runtime_class"],
            "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
            "elapsed_ns": time.monotonic_ns() - started,
        }
        if p.returncode != 0:
            raise RuntimeError("registered job failed: " + canonical(observed).decode())
        return observed

    def _start_runtime(self, spec: dict, restarted: bool = False) -> Dict[str, Any]:
        rid = spec["runtime_id"]
        with self._lock:
            proc = self._processes.get(rid)
            if not proc:
                proc = ManagedProcess(rid, list(spec["argv"]))
                self._processes[rid] = proc
            pid = proc.restart() if restarted and proc.alive() else proc.start()
            observed = proc.snapshot()
            self.registry.upsert({
                **spec, "pid": pid, "generation": observed["generation"], "desired_state": "RUNNING",
                "observed_state": "RUNNING" if observed["alive"] else "FAILED",
                "restart_count": observed["restart_count"], "last_readback": observed,
                "last_failure": observed["last_failure"],
            })
            return {"runtime_id": rid, **observed}

    def _stop_runtime(self, spec: dict) -> Dict[str, Any]:
        rid = spec["runtime_id"]
        with self._lock:
            proc = self._processes.get(rid)
            if proc:
                proc.stop()
                observed = proc.snapshot()
            else:
                observed = {"pid": None, "alive": False, "exit_code": None, "generation": 0, "restart_count": 0, "last_failure": None}
            current = self.registry.get(rid)
            if current:
                self.registry.observe(rid, pid=None, desired_state="STOPPED", observed_state="STOPPED", last_readback=observed)
            return {"runtime_id": rid, **observed}

    def _readback_runtime(self, spec: dict) -> Dict[str, Any]:
        rid = spec["runtime_id"]
        with self._lock:
            proc = self._processes.get(rid)
            observed = proc.snapshot() if proc else {"pid": None, "alive": False, "exit_code": None, "generation": 0, "restart_count": 0, "last_failure": "NOT_OWNED_BY_THIS_FABRIC_PROCESS"}
            registered = self.registry.get(rid)
            return {"runtime_id": rid, "process": observed, "registry": registered}

    def health(self) -> Dict[str, Any]:
        return {
            "status": "PASS",
            "fabric": FABRIC_ID,
            "schema": SCHEMA,
            "routes": self.available_routes(),
            "runtime_count": len(self.registry.list()),
            "proof_required": self.policy.require_proof,
        }
