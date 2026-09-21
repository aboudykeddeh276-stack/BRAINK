#!/usr/bin/env python3
"""BRAINK governed node-template registry and instance factory.

Templates are stable governed definitions. Instances reference templates by
identity/version and receive independent state, observer relations, integration
edges and attribution extensions. No opaque markup copy is used as identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / ".kex" / "state" / "node_templates.sqlite"

def canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()

def now_ns() -> int:
    return time.time_ns()

class NodeTemplateRegistry:
    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS templates(
              template_id TEXT NOT NULL,
              version TEXT NOT NULL,
              definition_id TEXT NOT NULL,
              body_json TEXT NOT NULL,
              proof_root TEXT NOT NULL,
              created_ns INTEGER NOT NULL,
              PRIMARY KEY(template_id, version)
            );
            CREATE TABLE IF NOT EXISTS instances(
              instance_id TEXT PRIMARY KEY,
              template_id TEXT NOT NULL,
              template_version TEXT NOT NULL,
              definition_id TEXT NOT NULL,
              lineage_root TEXT NOT NULL,
              instance_state_json TEXT NOT NULL,
              observer_relations_json TEXT NOT NULL,
              integration_edges_json TEXT NOT NULL,
              attribution_json TEXT NOT NULL,
              proof_root TEXT NOT NULL,
              created_ns INTEGER NOT NULL,
              updated_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event TEXT NOT NULL,
              previous_proof_root TEXT NOT NULL,
              proof_root TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_ns INTEGER NOT NULL
            );
            """)

    def db(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def receipt(self, event: str, **payload: Any) -> Dict[str, Any]:
        t = now_ns()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT proof_root FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else "0" * 64
            body = {"event": event, "timestamp_ns": t, "previous_proof_root": prev, **payload}
            body["proof_root"] = sha(body)
            db.execute(
                "INSERT INTO receipts(event,previous_proof_root,proof_root,payload_json,created_ns) VALUES(?,?,?,?,?)",
                (event, prev, body["proof_root"], canon(body), t),
            )
            db.commit()
        return body

    def register_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        required = [
            "template_id","definition_id","type","sector","role","version",
            "capability_class","typed_inputs","typed_outputs","attributes",
            "attribution_graph","integration_contract","policy_bindings",
            "compatibility","lifecycle","authorship"
        ]
        missing = [k for k in required if k not in template]
        if missing:
            raise ValueError("TEMPLATE_MISSING:" + ",".join(missing))
        if template["capability_class"] not in {"DUMB","SMART"}:
            raise ValueError("BAD_CAPABILITY_CLASS")
        body = dict(template)
        body.pop("proof_root", None)
        body["proof_root"] = sha(body)
        with self.db() as db:
            db.execute(
                """INSERT INTO templates(template_id,version,definition_id,body_json,proof_root,created_ns)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(template_id,version) DO UPDATE SET
                   definition_id=excluded.definition_id,
                   body_json=excluded.body_json,
                   proof_root=excluded.proof_root""",
                (body["template_id"], body["version"], body["definition_id"], canon(body), body["proof_root"], now_ns())
            )
        self.receipt("TEMPLATE_REGISTERED", template_id=body["template_id"], version=body["version"], template_proof_root=body["proof_root"])
        return body

    def get_template(self, template_id: str, version: str) -> Dict[str, Any]:
        with self.db() as db:
            row = db.execute("SELECT body_json FROM templates WHERE template_id=? AND version=?", (template_id, version)).fetchone()
        if not row:
            raise KeyError(f"TEMPLATE_NOT_FOUND:{template_id}@{version}")
        return json.loads(row[0])

    def instantiate(
        self,
        template_id: str,
        version: str,
        *,
        instance_id: Optional[str] = None,
        initial_state: Optional[Dict[str, Any]] = None,
        observer_relations: Optional[list] = None,
        integration_edges: Optional[list] = None,
        attribution_extensions: Optional[list] = None,
    ) -> Dict[str, Any]:
        template = self.get_template(template_id, version)
        instance_id = instance_id or f"node:{uuid.uuid4()}"
        lineage = {
            "template_id": template["template_id"],
            "definition_id": template["definition_id"],
            "template_version": template["version"],
            "template_proof_root": template["proof_root"],
            "authorship": template["authorship"],
        }
        lineage_root = sha(lineage)
        t = now_ns()
        instance = {
            "instance_id": instance_id,
            "template_id": template["template_id"],
            "definition_id": template["definition_id"],
            "template_version": template["version"],
            "lineage_root": lineage_root,
            "instance_state": initial_state or {},
            "observer_relations": observer_relations or [],
            "integration_edges": integration_edges or [],
            "attribution": {
                "template_attribution_graph": template["attribution_graph"],
                "instance_extensions": attribution_extensions or [],
            },
            "created_ns": t,
        }
        instance["proof_root"] = sha(instance)
        with self.db() as db:
            db.execute(
                """INSERT INTO instances(instance_id,template_id,template_version,definition_id,lineage_root,
                   instance_state_json,observer_relations_json,integration_edges_json,attribution_json,
                   proof_root,created_ns,updated_ns) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    instance_id, template["template_id"], template["version"], template["definition_id"], lineage_root,
                    canon(instance["instance_state"]), canon(instance["observer_relations"]), canon(instance["integration_edges"]),
                    canon(instance["attribution"]), instance["proof_root"], t, t
                )
            )
        self.receipt("NODE_INSTANTIATED", instance_id=instance_id, template_id=template_id, version=version, lineage_root=lineage_root, instance_proof_root=instance["proof_root"])
        return instance

def self_test() -> Dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = NodeTemplateRegistry(Path(td) / "nodes.sqlite")
        tpl = r.register_template({
            "template_id":"template:hci.status-card",
            "definition_id":"definition:hci.status-card",
            "type":"NODE_TEMPLATE","sector":"HCI","role":"STATUS_CARD","version":"1.0.0",
            "capability_class":"DUMB",
            "typed_inputs":{"label":"string","state":"enum"},
            "typed_outputs":{"render_model":"object"},
            "attributes":[{"name":"compact","value_type":"boolean","value":True,"source":"definition:hci.status-card","source_version":"1.0.0"}],
            "attribution_graph":[{"type":"AUTHORED_BY","target":"Keddeh Systems"}],
            "integration_contract":{"interfaces":["status.read"]},
            "policy_bindings":["policy:hci.readonly"],
            "compatibility":{"runtime":">=1"},
            "lifecycle":"IMMUTABLE",
            "authorship":{"authority":"Keddeh Systems"}
        })
        a = r.instantiate(tpl["template_id"], tpl["version"], instance_id="node:a", initial_state={"state":"UP"})
        b = r.instantiate(tpl["template_id"], tpl["version"], instance_id="node:b", initial_state={"state":"DOWN"})
        assert a["lineage_root"] == b["lineage_root"]
        assert a["instance_id"] != b["instance_id"]
        assert a["instance_state"] != b["instance_state"]
        return {"status":"PASS","checks":["template_registration","lineage_preservation","independent_instance_state"]}

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        print(json.dumps(self_test(), indent=2))
        return 0
    p.print_help()
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
