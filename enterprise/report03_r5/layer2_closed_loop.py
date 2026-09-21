#!/usr/bin/env python3
"""Closed-loop Layer-2 reconciler with an observable local manifestation actuator."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib, json, os, sqlite3

from tot_safety_kernel import canonical, h
from distributed_coordinate_directory import DirectoryCluster

SCHEMA = "keddeh.layer2-closed-loop.v2"


def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_bytes(value: Any) -> bytes:
    if isinstance(value, bytes): return value
    if isinstance(value, str): return value.encode("utf-8")
    return (canonical(value) + "\n").encode("utf-8")


def safe_relpath(p: str) -> str:
    path = Path(p)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("ACTUATOR_PATH_OUTSIDE_MANAGED_ROOT")
    return path.as_posix()


@dataclass(frozen=True)
class ClosedLoopPlan:
    schema: str
    coordinate: str
    directory_replica: str
    directory_root: str
    accepted_state_root: str
    commit_index: int
    desired_root: str
    observed_root: str
    actions: tuple[dict[str, Any], ...]
    plan_root: str


class SandboxActuator:
    """Concrete test actuator: files are the manifestation surface, receipts are durable."""
    def __init__(self, root: str | Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.receipt_db = self.root.parent / f"{self.root.name}.actuator.sqlite3"
        self.conn = sqlite3.connect(self.receipt_db)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("CREATE TABLE IF NOT EXISTS receipts(idempotency_key TEXT PRIMARY KEY, receipt_json TEXT NOT NULL)")
        self.conn.commit()

    def close(self): self.conn.close()

    def sqlite_mode(self) -> dict[str, Any]:
        return {"journal_mode": str(self.conn.execute("PRAGMA journal_mode").fetchone()[0]).upper(), "synchronous": int(self.conn.execute("PRAGMA synchronous").fetchone()[0]), "db_path": str(self.receipt_db)}

    def observed(self) -> dict[str, dict[str, Any]]:
        out = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                data = p.read_bytes(); rel = p.relative_to(self.root).as_posix()
                out[rel] = {"sha256": bytes_hash(data), "bytes": len(data)}
        return out

    def _fsync_dir(self, directory: Path) -> None:
        fd = os.open(directory, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

    def _write_atomic(self, rel: str, data: bytes) -> None:
        rel = safe_relpath(rel); target = self.root / rel; target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, target); self._fsync_dir(target.parent)

    def _receipt(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT receipt_json FROM receipts WHERE idempotency_key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def apply(self, action: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        prior = self._receipt(idempotency_key)
        if prior:
            return {**prior, "idempotent_replay": True}
        rel = safe_relpath(action["path"]); target = self.root / rel
        before = bytes_hash(target.read_bytes()) if target.exists() else None
        kind = action["action"]
        if kind in ("MATERIALISE", "REPLACE"):
            data = content_bytes(action["content"])
            self._write_atomic(rel, data)
        elif kind == "DETACH":
            if target.exists(): target.unlink(); self._fsync_dir(target.parent)
        else:
            raise ValueError(f"UNKNOWN_ACTUATOR_ACTION:{kind}")
        after = bytes_hash(target.read_bytes()) if target.exists() else None
        receipt = {"state":"ACTUATOR_EFFECT_APPLIED","action":kind,"path":rel,"before_sha256":before,"after_sha256":after,"idempotency_key":idempotency_key}
        with self.conn:
            self.conn.execute("INSERT INTO receipts(idempotency_key,receipt_json) VALUES(?,?)", (idempotency_key, canonical(receipt)))
        return receipt


class ClosedLoopReconciler:
    def __init__(self, directory: DirectoryCluster, replica_id: str, actuator: SandboxActuator):
        self.directory = directory; self.replica_id = replica_id; self.actuator = actuator

    def plan(self, coordinate: str) -> ClosedLoopPlan:
        resolved = self.directory.resolve(self.replica_id, coordinate)
        if resolved["state"] != "RESOLVED_ACCEPTED_COORDINATE": raise ValueError("UNKNOWN_COORDINATE")
        desired_files = resolved["record"].get("desired", {}).get("managed_files", {})
        desired_norm = {safe_relpath(k): {"content": v, "sha256": bytes_hash(content_bytes(v))} for k,v in desired_files.items()}
        observed = self.actuator.observed()
        actions = []
        for rel in sorted(desired_norm):
            d = desired_norm[rel]; o = observed.get(rel)
            if o is None:
                actions.append({"action":"MATERIALISE","path":rel,"content":d["content"],"desired_sha256":d["sha256"]})
            elif o["sha256"] != d["sha256"]:
                actions.append({"action":"REPLACE","path":rel,"content":d["content"],"from_sha256":o["sha256"],"desired_sha256":d["sha256"]})
        for rel in sorted(set(observed) - set(desired_norm)):
            actions.append({"action":"DETACH","path":rel,"from_sha256":observed[rel]["sha256"]})
        body = {
            "schema":SCHEMA,"coordinate":coordinate,"directory_replica":self.replica_id,
            "directory_root":resolved["directory_root"],"accepted_state_root":resolved["accepted_state_root"],"commit_index":resolved["commit_index"],
            "desired_root":h(desired_norm),"observed_root":h(observed),"actions":actions,
        }
        return ClosedLoopPlan(**{k:v for k,v in body.items() if k!="actions"}, actions=tuple(actions), plan_root=h(body))

    def apply(self, plan: ClosedLoopPlan) -> dict[str, Any]:
        current = self.directory.resolve(plan.directory_replica, plan.coordinate)
        if current["directory_root"] != plan.directory_root or current["accepted_state_root"] != plan.accepted_state_root or current["commit_index"] != plan.commit_index:
            raise RuntimeError("RECONCILE_PLAN_STALE_ACCEPTED_OR_DIRECTORY_STATE_CHANGED")
        if not plan.actions:
            return {"state":"NOOP_ALREADY_CONVERGED","plan_root":plan.plan_root,"results":[]}
        results = []
        for i, action in enumerate(plan.actions, 1):
            key = h({"plan_root":plan.plan_root,"ordinal":i,"action":action})
            results.append(self.actuator.apply(action, idempotency_key=key))
        return {"state":"PLAN_APPLIED_TO_SANDBOX_MANIFESTATION","plan_root":plan.plan_root,"results":results,"post_observed_root":h(self.actuator.observed())}

    def reconcile_until_converged(self, coordinate: str, *, max_passes: int = 4) -> dict[str, Any]:
        passes=[]
        for _ in range(max_passes):
            plan=self.plan(coordinate); out=self.apply(plan); passes.append({"plan":asdict(plan),"apply":out})
            if out["state"]=="NOOP_ALREADY_CONVERGED":
                return {"state":"CLOSED_LOOP_CONVERGED","passes":passes,"observed":self.actuator.observed()}
        return {"state":"CLOSED_LOOP_NOT_CONVERGED","passes":passes,"observed":self.actuator.observed()}