from __future__ import annotations

from pathlib import Path
from typing import Any
import fcntl
import hashlib
import json
import os
import tempfile


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class VersionedGlobalKnowledge:
    """Versioned governed IL-LLM delta registry; never mutates execution directly."""

    SCHEMA = "braink.global-illlm.r40/v1"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        if not self.path.exists():
            self._write_atomic({"schema": self.SCHEMA, "version": 0, "relations": {}, "updates": [], "subscribers": {}})

    def _read(self) -> dict[str, Any]:
        body = json.loads(self.path.read_text(encoding="utf-8"))
        if body.get("schema") != self.SCHEMA:
            raise RuntimeError("GLOBAL_ILLLM_SCHEMA_MISMATCH")
        return body

    def _write_atomic(self, body: dict[str, Any]) -> None:
        raw = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw); fh.flush(); os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
        finally:
            if os.path.exists(tmp_name): os.unlink(tmp_name)

    def snapshot(self) -> dict[str, Any]:
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH); body = self._read(); fcntl.flock(lock, fcntl.LOCK_UN)
        return {**body, "state_root": root(body)}

    def subscribe(self, node_id: str, data_classes: list[str]) -> dict[str, Any]:
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX); body = self._read()
            body["subscribers"][str(node_id)] = sorted(set(map(str, data_classes)))
            self._write_atomic(body); fcntl.flock(lock, fcntl.LOCK_UN)
        return {"status": "SUBSCRIBED", "node_id": str(node_id), "version": body["version"]}

    def apply_delta(self, *, source_node: str, source_event: str, data_class: str, previous_version: int,
                    relation_delta: dict[str, Any], provenance: dict[str, Any], authority: str,
                    validation: dict[str, Any], ledger_reference: str) -> dict[str, Any]:
        if validation.get("status") != "VALIDATED": raise ValueError("GLOBAL_DELTA_REQUIRES_VALIDATION")
        if not str(authority).strip(): raise ValueError("GLOBAL_DELTA_AUTHORITY_REQUIRED")
        if not str(ledger_reference).strip(): raise ValueError("GLOBAL_DELTA_LEDGER_REFERENCE_REQUIRED")
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX); body = self._read(); current = int(body["version"])
            if int(previous_version) != current:
                raise RuntimeError(f"STALE_GLOBAL_VERSION:expected={current}:received={previous_version}")
            proposed = current + 1
            material = {"source_node": str(source_node), "source_event": str(source_event), "data_class": str(data_class),
                        "previous_version": current, "proposed_version": proposed, "relation_delta": relation_delta,
                        "provenance": provenance, "authority": str(authority), "validation": validation,
                        "ledger_reference": str(ledger_reference)}
            update_id = "UPDATE-" + root(material)[:24]
            relations = dict(body["relations"])
            for key, value in relation_delta.get("set", {}).items(): relations[str(key)] = value
            for key in relation_delta.get("delete", []): relations.pop(str(key), None)
            body["relations"] = relations; body["updates"].append({"update_id": update_id, **material}); body["version"] = proposed
            self._write_atomic(body); fcntl.flock(lock, fcntl.LOCK_UN)
        subscribers = [node_id for node_id, classes in body["subscribers"].items() if "*" in classes or str(data_class) in classes]
        return {"status": "COMMITTED", "update_id": update_id, "previous_version": current, "version": proposed,
                "state_root": root(body), "subscriber_notifications": sorted(subscribers), "execution_mutation": False}
