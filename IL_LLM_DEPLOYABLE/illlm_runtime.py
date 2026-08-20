#!/usr/bin/env python3
"""IL-LLM deployable reference runtime.

Isolated build candidate: does not replace BRAINK product runtime.
Implements evidence-first intake, deterministic routing, bounded local retrieval,
pre-action admission, append-only receipts, and health/status surfaces.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-candidate"
MAX_FILE_BYTES = 2_000_000
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".py", ".swift", ".ts", ".tsx", ".js", ".html", ".yaml", ".yml"}


def canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()

def safe_under(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    candidate = candidate.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes configured root")
    return candidate

@dataclass(frozen=True)
class Evidence:
    path: str
    sha256: str
    bytes: int

@dataclass(frozen=True)
class Admission:
    admitted: bool
    failures: tuple[str, ...]
    qualification_ceiling: str

class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def append(self, event: dict) -> dict:
        previous = "GENESIS"
        if self.path.exists():
            lines = [x for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]
            if lines:
                previous = json.loads(lines[-1])["event_hash"]
        body = {**event, "previous_hash": previous}
        body["event_hash"] = digest(body)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")
        return body

class ILLLM:
    def __init__(self, root: Path, state: Path):
        self.root = root.resolve()
        self.state = state.resolve()
        self.ledger = Ledger(self.state / "ledger.jsonl")
    def inventory(self) -> list[Evidence]:
        out: list[Evidence] = []
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or p.is_symlink() or p.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                size = p.stat().st_size
                if size > MAX_FILE_BYTES: continue
                data = p.read_bytes()
            except OSError:
                continue
            out.append(Evidence(str(p.relative_to(self.root)), hashlib.sha256(data).hexdigest(), len(data)))
        return out
    def retrieve(self, query: str, limit: int = 8) -> list[dict]:
        terms = [t for t in re.findall(r"[a-z0-9_\-]+", query.lower()) if len(t) > 1]
        scored = []
        for ev in self.inventory():
            p = safe_under(self.root, self.root / ev.path)
            try: text = p.read_text(encoding="utf-8", errors="replace")[:120_000]
            except OSError: continue
            low = text.lower()
            score = sum(low.count(t) for t in terms) + sum(2 for t in terms if t in ev.path.lower())
            if score:
                snippets = [line.strip() for line in text.splitlines() if any(t in line.lower() for t in terms)][:4]
                scored.append((score, ev.path, ev.sha256, snippets))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [{"score": s, "path": p, "sha256": h, "snippets": sn} for s,p,h,sn in scored[:limit]]
    def admit(self, objective: str, evidence: list[dict]) -> Admission:
        failures = []
        if not objective.strip(): failures.append("EMPTY_OBJECTIVE")
        if not evidence: failures.append("NO_LOCAL_EVIDENCE")
        return Admission(not failures, tuple(failures), "LOCAL_EVIDENCE_SCOPED")
    def run(self, objective: str) -> dict:
        evidence = self.retrieve(objective)
        admission = self.admit(objective, evidence)
        packet = {"version": VERSION, "objective": objective, "evidence": evidence, "admission": asdict(admission)}
        packet["packet_hash"] = digest(packet)
        receipt = self.ledger.append({"type":"ILLLM_OPERATION", "timestamp":int(time.time()), "packet":packet})
        return {"status":"DONE" if admission.admitted else "ROUTED", "packet":packet, "receipt":receipt}
    def health(self) -> dict:
        inv = self.inventory()
        return {"status":"ok", "version":VERSION, "root":str(self.root), "indexed_files":len(inv), "ledger":str(self.ledger.path)}

def main() -> int:
    ap = argparse.ArgumentParser(prog="illlm")
    ap.add_argument("--root", default=os.environ.get("ILLLM_ROOT", "."))
    ap.add_argument("--state", default=os.environ.get("ILLLM_STATE", "./.illlm_state"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health")
    run = sub.add_parser("run"); run.add_argument("objective")
    ret = sub.add_parser("retrieve"); ret.add_argument("query"); ret.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()
    runtime = ILLLM(Path(args.root), Path(args.state))
    if args.cmd == "health": out = runtime.health()
    elif args.cmd == "retrieve": out = runtime.retrieve(args.query, args.limit)
    else: out = runtime.run(args.objective)
    print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
    return 0
if __name__ == "__main__": raise SystemExit(main())
