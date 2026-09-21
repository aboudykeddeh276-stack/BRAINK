#!/usr/bin/env python3
"""BRAINK governed node-template registry and lineage-aware instance runtime.

A template is a stable governed definition. An instance references that definition
and owns independent state, observer relations, integration edges and attribution.
Rendered markup is output only and never establishes node identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = Path(__import__("os").environ.get("BRAINK_NODE_TEMPLATE_DB", str(ROOT / ".kex" / "state" / "node_templates.sqlite")))
CAPABILITY_CLASSES = {"DUMB_NODE", "SMART_NODE", "AGENTIC_NODE", "SYSTEM_NODE"}

def canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()

def now_ns() -> int:
    return time.time_ns()

def edge_id(instance_id: str, direction: str, edge: Dict[str, Any]) -> str:
    return f"{direction}:{sha({'instance_id':instance_id,'edge':edge})[:20]}"

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
            CREATE INDEX IF NOT EXISTS idx_instances_template ON instances(template_id,template_version);
            """)

    def db(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
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
            db.execute("INSERT INTO receipts(event,previous_proof_root,proof_root,payload_json,created_ns) VALUES(?,?,?,?,?)",
                       (event, prev, body["proof_root"], canon(body), t))
            db.commit()
        return body

    def register_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        required = ["template_id","definition_id","type","sector","role","version","capability_class",
                    "typed_inputs","typed_outputs","attributes","attribution_graph","integration_contract",
                    "policy_bindings","compatibility","lifecycle","authorship"]
        missing = [k for k in required if k not in template]
        if missing:
            raise ValueError("TEMPLATE_MISSING:" + ",".join(missing))
        cc = str(template["capability_class"])
        if cc in {"DUMB","SMART"}:
            cc += "_NODE"
        if cc not in CAPABILITY_CLASSES:
            raise ValueError("BAD_CAPABILITY_CLASS:" + cc)
        body = dict(template)
        body["capability_class"] = cc
        body.pop("proof_root", None)
        body["proof_root"] = sha(body)
        with self.db() as db:
            existing = db.execute("SELECT proof_root FROM templates WHERE template_id=? AND version=?",
                                  (body["template_id"], body["version"])).fetchone()
            if existing and existing[0] != body["proof_root"]:
                raise ValueError("IMMUTABLE_TEMPLATE_VERSION_CONFLICT")
            db.execute("""INSERT OR IGNORE INTO templates(template_id,version,definition_id,body_json,proof_root,created_ns)
                          VALUES(?,?,?,?,?,?)""",
                       (body["template_id"],body["version"],body["definition_id"],canon(body),body["proof_root"],now_ns()))
        self.receipt("TEMPLATE_REGISTERED",template_id=body["template_id"],version=body["version"],template_proof_root=body["proof_root"])
        return body

    def get_template(self, template_id: str, version: str) -> Dict[str, Any]:
        with self.db() as db:
            row = db.execute("SELECT body_json FROM templates WHERE template_id=? AND version=?",(template_id,version)).fetchone()
        if not row:
            raise KeyError(f"TEMPLATE_NOT_FOUND:{template_id}@{version}")
        return json.loads(row[0])

    def list_templates(self) -> List[Dict[str, Any]]:
        with self.db() as db:
            rows = db.execute("SELECT body_json FROM templates ORDER BY template_id,version").fetchall()
        return [json.loads(r[0]) for r in rows]

    def get_instance(self, instance_id: str) -> Dict[str, Any]:
        with self.db() as db:
            row = db.execute("SELECT * FROM instances WHERE instance_id=?",(instance_id,)).fetchone()
        if not row:
            raise KeyError("INSTANCE_NOT_FOUND:" + instance_id)
        template=self.get_template(row["template_id"],row["template_version"])
        return {
            "instance_id":row["instance_id"],"template_id":row["template_id"],"template_version":row["template_version"],
            "definition_id":row["definition_id"],"lineage_root":row["lineage_root"],
            "capability_class":template["capability_class"],
            "typed_inputs":template["typed_inputs"],"typed_outputs":template["typed_outputs"],
            "attributes":template["attributes"],
            "instance_state":json.loads(row["instance_state_json"]),
            "observer_relations":json.loads(row["observer_relations_json"]),
            "integration_edges":json.loads(row["integration_edges_json"]),
            "attribution":json.loads(row["attribution_json"]),
            "proof_root":row["proof_root"],"created_ns":row["created_ns"],"updated_ns":row["updated_ns"]
        }

    def list_instances(self, template_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.db() as db:
            rows = db.execute("SELECT instance_id FROM instances" + (" WHERE template_id=?" if template_id else "") + " ORDER BY instance_id",
                              ((template_id,) if template_id else ())).fetchall()
        return [self.get_instance(r[0]) for r in rows]

    def instantiate(self, template_id: str, version: str, *, instance_id: Optional[str] = None,
                    instance_key: Optional[str] = None, initial_state: Optional[Dict[str, Any]] = None,
                    observer_relations: Optional[list] = None, integration_edges: Optional[list] = None,
                    attribution_extensions: Optional[list] = None) -> Dict[str, Any]:
        template = self.get_template(template_id, version)
        lineage = {
            "template_id":template["template_id"],"definition_id":template["definition_id"],
            "template_version":template["version"],"template_proof_root":template["proof_root"],
            "authorship":template["authorship"]
        }
        lineage_root = sha(lineage)
        if not instance_id:
            if not instance_key:
                raise ValueError("INSTANCE_ID_OR_INSTANCE_KEY_REQUIRED")
            instance_id = "node:" + sha({"lineage_root":lineage_root,"instance_key":instance_key})[:24]

        edges = []
        for e in (integration_edges or []):
            item = dict(e)
            item.setdefault("edge_id", edge_id(instance_id, str(item.get("direction","EDGE")), item))
            edges.append(item)
        t = now_ns()
        base = {
            "instance_id":instance_id,"template_id":template["template_id"],"definition_id":template["definition_id"],
            "template_version":template["version"],"lineage_root":lineage_root,
            "capability_class":template["capability_class"],"typed_inputs":template["typed_inputs"],
            "typed_outputs":template["typed_outputs"],"attributes":template["attributes"],
            "instance_state":initial_state or {},"observer_relations":observer_relations or [],
            "integration_edges":edges,
            "attribution":{"template_attribution_graph":template["attribution_graph"],"instance_extensions":attribution_extensions or []},
            "created_ns":t
        }
        base["proof_root"] = sha(base)
        with self.db() as db:
            db.execute("""INSERT INTO instances(instance_id,template_id,template_version,definition_id,lineage_root,
              instance_state_json,observer_relations_json,integration_edges_json,attribution_json,proof_root,created_ns,updated_ns)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
              (instance_id,template["template_id"],template["version"],template["definition_id"],lineage_root,
               canon(base["instance_state"]),canon(base["observer_relations"]),canon(base["integration_edges"]),
               canon(base["attribution"]),base["proof_root"],t,t))
        self.receipt("NODE_INSTANTIATED",instance_id=instance_id,template_id=template_id,version=version,
                     lineage_root=lineage_root,instance_proof_root=base["proof_root"])
        return base

    def mutate_instance(self, instance_id: str, *, expected_proof_root: str, state: Optional[Dict[str,Any]] = None,
                        observer_relations: Optional[list] = None, integration_edges: Optional[list] = None,
                        attribution_extensions: Optional[list] = None) -> Dict[str, Any]:
        current = self.get_instance(instance_id)
        if current["proof_root"] != expected_proof_root:
            raise ValueError("INSTANCE_PROOF_CONFLICT")
        updated = dict(current)
        if state is not None: updated["instance_state"] = state
        if observer_relations is not None: updated["observer_relations"] = observer_relations
        if integration_edges is not None:
            edges=[]
            for e in integration_edges:
                item=dict(e); item.setdefault("edge_id",edge_id(instance_id,str(item.get("direction","EDGE")),item)); edges.append(item)
            updated["integration_edges"]=edges
        if attribution_extensions is not None:
            updated["attribution"]["instance_extensions"] = attribution_extensions
        updated["updated_ns"] = now_ns()
        updated["proof_root"] = sha({k:v for k,v in updated.items() if k!="proof_root"})
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT proof_root FROM instances WHERE instance_id=?",(instance_id,)).fetchone()
            if not row or row[0] != expected_proof_root:
                raise ValueError("INSTANCE_PROOF_CONFLICT")
            db.execute("""UPDATE instances SET instance_state_json=?,observer_relations_json=?,integration_edges_json=?,
                         attribution_json=?,proof_root=?,updated_ns=? WHERE instance_id=?""",
                       (canon(updated["instance_state"]),canon(updated["observer_relations"]),canon(updated["integration_edges"]),
                        canon(updated["attribution"]),updated["proof_root"],updated["updated_ns"],instance_id))
            db.commit()
        self.receipt("NODE_INSTANCE_MUTATED",instance_id=instance_id,previous_instance_proof_root=expected_proof_root,
                     instance_proof_root=updated["proof_root"])
        return updated

def self_test() -> Dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r=NodeTemplateRegistry(Path(td)/"nodes.sqlite")
        tpl=r.register_template({
          "template_id":"TPL_HCI_STATUS_CARD_V1","definition_id":"HCI_STATUS_CARD","type":"NODE_TEMPLATE","sector":"HCI",
          "role":"STATUS_CARD","version":"1.0.0","capability_class":"DUMB_NODE",
          "typed_inputs":{"label":"string","state":"enum"},"typed_outputs":{"render_model":"object"},
          "attributes":[{"name":"compact","value_type":"boolean","value":True,"source":"HCI_STATUS_CARD","source_version":"1.0.0"}],
          "attribution_graph":[{"type":"AUTHORED_BY","target":"Keddeh Systems"}],
          "integration_contract":{"interfaces":["status.read"]},"policy_bindings":["policy:hci.readonly"],
          "compatibility":{"runtime":">=1"},"lifecycle":"IMMUTABLE","authorship":{"authority":"Keddeh Systems"}
        })
        a=r.instantiate(tpl["template_id"],tpl["version"],instance_key="a",initial_state={"state":"UP"})
        b=r.instantiate(tpl["template_id"],tpl["version"],instance_key="b",initial_state={"state":"DOWN"})
        assert a["lineage_root"]==b["lineage_root"] and a["instance_id"]!=b["instance_id"] and a["instance_state"]!=b["instance_state"]
        a2=r.mutate_instance(a["instance_id"],expected_proof_root=a["proof_root"],state={"state":"DEGRADED"})
        assert a2["proof_root"]!=a["proof_root"] and r.get_instance(b["instance_id"])["instance_state"]["state"]=="DOWN"
        try:
            r.mutate_instance(a["instance_id"],expected_proof_root=a["proof_root"],state={})
            raise AssertionError("stale proof accepted")
        except ValueError:
            pass
        return {"status":"PASS","checks":["template_immutability","lineage_preservation","independent_instance_state","optimistic_mutation","stale_proof_rejection"]}

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--db",default=str(DEFAULT_DB)); p.add_argument("--self-test",action="store_true")
    p.add_argument("--list-templates",action="store_true"); p.add_argument("--list-instances",action="store_true")
    a=p.parse_args()
    if a.self_test: print(json.dumps(self_test(),indent=2)); return 0
    r=NodeTemplateRegistry(Path(a.db))
    if a.list_templates: print(json.dumps(r.list_templates(),indent=2)); return 0
    if a.list_instances: print(json.dumps(r.list_instances(),indent=2)); return 0
    p.print_help(); return 2
if __name__=="__main__": raise SystemExit(main())
