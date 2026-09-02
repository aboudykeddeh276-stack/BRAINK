from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib, json, sqlite3, time, uuid


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ResearchNode:
    node_id: str
    node_type: str
    term: str
    definition: str
    subject: str
    topic: str
    matter: str
    authority_scope: str
    state: str
    revision: int
    created_ns: int
    updated_ns: int


class ExposedILLLM:
    """KEDDEH SYSTEMS exposed IL-LLM research plane."""

    NODE_TYPES = {
        "WORD", "DEFINITION", "SUBJECT", "TOPIC", "MATTER", "FUNCTION",
        "ADAPTER", "CONTROL", "CLAIM", "EVIDENCE", "SECTOR", "SERVICE",
        "WORK_MODULE", "AGENT", "RUNTIME"
    }

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _db(self):
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _init(self):
        db = self._db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS nodes(
          node_id TEXT PRIMARY KEY, node_type TEXT NOT NULL, term TEXT NOT NULL,
          definition TEXT NOT NULL, subject TEXT NOT NULL, topic TEXT NOT NULL,
          matter TEXT NOT NULL, authority_scope TEXT NOT NULL, state TEXT NOT NULL,
          revision INTEGER NOT NULL, created_ns INTEGER NOT NULL, updated_ns INTEGER NOT NULL,
          node_root TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_nodes_term ON nodes(term);
        CREATE INDEX IF NOT EXISTS idx_nodes_subject ON nodes(subject);
        CREATE INDEX IF NOT EXISTS idx_nodes_topic ON nodes(topic);
        CREATE INDEX IF NOT EXISTS idx_nodes_matter ON nodes(matter);
        CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY, node_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS relations(
          relation_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, predicate TEXT NOT NULL,
          target_id TEXT NOT NULL, created_ns INTEGER NOT NULL, relation_root TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence(
          evidence_id TEXT PRIMARY KEY, node_id TEXT NOT NULL, evidence_type TEXT NOT NULL,
          source_ref TEXT NOT NULL, content_root TEXT NOT NULL, confidence REAL NOT NULL,
          observed_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS revisions(
          revision_id TEXT PRIMARY KEY, node_id TEXT NOT NULL, predecessor_root TEXT NOT NULL,
          successor_root TEXT NOT NULL, reason TEXT NOT NULL, created_ns INTEGER NOT NULL
        );
        """)
        db.commit()
        db.close()

    def upsert(self, *, node_type: str, term: str, definition: str = "", subject: str = "",
               topic: str = "", matter: str = "", authority_scope: str = "KEDDEH_SYSTEMS",
               state: str = "CURRENT") -> ResearchNode:
        node_type = node_type.upper()
        if node_type not in self.NODE_TYPES:
            raise ValueError("UNSUPPORTED_NODE_TYPE")
        db = self._db()
        try:
            row = db.execute("SELECT * FROM nodes WHERE term=? AND node_type=?", (term, node_type)).fetchone()
            now = time.time_ns()
            if row:
                predecessor = row["node_root"]
                revision = row["revision"] + 1
                node = ResearchNode(row["node_id"], node_type, term, definition, subject, topic, matter,
                                    authority_scope, state, revision, row["created_ns"], now)
                node_root = root(asdict(node))
                db.execute("""UPDATE nodes SET definition=?,subject=?,topic=?,matter=?,authority_scope=?,
                           state=?,revision=?,updated_ns=?,node_root=? WHERE node_id=?""",
                           (definition, subject, topic, matter, authority_scope, state, revision, now,
                            node_root, node.node_id))
                db.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?)",
                           ("REV-" + uuid.uuid4().hex[:16], node.node_id, predecessor, node_root, "UPSERT", now))
            else:
                node_id = "NODE-" + uuid.uuid4().hex[:16]
                node = ResearchNode(node_id, node_type, term, definition, subject, topic, matter,
                                    authority_scope, state, 1, now, now)
                node_root = root(asdict(node))
                db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (node_id, node_type, term, definition, subject, topic, matter, authority_scope,
                            state, 1, now, now, node_root))
            db.commit()
            return node
        finally:
            db.close()

    def alias(self, node_id: str, *aliases: str) -> None:
        db = self._db()
        try:
            for alias in aliases:
                db.execute("INSERT OR REPLACE INTO aliases VALUES(?,?)", (alias, node_id))
            db.commit()
        finally:
            db.close()

    def relate(self, source_id: str, predicate: str, target_id: str) -> Dict[str, Any]:
        relation_id = "REL-" + uuid.uuid4().hex[:16]
        body = {"source_id": source_id, "predicate": predicate, "target_id": target_id}
        relation_root = root(body)
        db = self._db()
        try:
            db.execute("INSERT INTO relations VALUES(?,?,?,?,?,?)",
                       (relation_id, source_id, predicate, target_id, time.time_ns(), relation_root))
            db.commit()
        finally:
            db.close()
        return {"relation_id": relation_id, **body, "relation_root": relation_root}

    def attach_evidence(self, node_id: str, evidence_type: str, source_ref: str,
                        content: Any, confidence: float = 1.0) -> Dict[str, Any]:
        evidence_id = "EV-" + uuid.uuid4().hex[:16]
        content_root = root(content)
        db = self._db()
        try:
            db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?)",
                       (evidence_id, node_id, evidence_type, source_ref, content_root,
                        float(confidence), time.time_ns()))
            db.commit()
        finally:
            db.close()
        return {"evidence_id": evidence_id, "node_id": node_id, "content_root": content_root,
                "confidence": confidence}

    def resolve(self, term_or_alias: str) -> Optional[Dict[str, Any]]:
        db = self._db()
        try:
            row = db.execute("SELECT * FROM nodes WHERE term=? ORDER BY revision DESC LIMIT 1", (term_or_alias,)).fetchone()
            if not row:
                alias = db.execute("SELECT node_id FROM aliases WHERE alias=?", (term_or_alias,)).fetchone()
                if alias:
                    row = db.execute("SELECT * FROM nodes WHERE node_id=?", (alias["node_id"],)).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        like = f"%{query}%"
        db = self._db()
        try:
            rows = db.execute("""SELECT * FROM nodes WHERE term LIKE ? OR definition LIKE ? OR
                subject LIKE ? OR topic LIKE ? OR matter LIKE ? ORDER BY revision DESC,term LIMIT ?""",
                              (like, like, like, like, like, limit)).fetchall()
            return [dict(row) for row in rows]
        finally:
            db.close()

    def research_packet(self, term: str) -> Dict[str, Any]:
        node = self.resolve(term)
        if not node:
            return {"status": "HOLE", "term": term}
        db = self._db()
        try:
            evidence = [dict(row) for row in db.execute("SELECT * FROM evidence WHERE node_id=?", (node["node_id"],)).fetchall()]
            relations = [dict(row) for row in db.execute(
                "SELECT * FROM relations WHERE source_id=? OR target_id=?",
                (node["node_id"], node["node_id"])).fetchall()]
            packet = {"status": "OK", "node": node, "evidence": evidence, "relations": relations}
            packet["packet_root"] = root(packet)
            return packet
        finally:
            db.close()
