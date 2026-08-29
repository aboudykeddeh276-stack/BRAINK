#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, time
from pathlib import Path
from typing import Any, Dict, List

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]*")

def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def load_active_story(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "active_story_lexicon.json")

def load_registry(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "il_llm_active_story_registry.json")

def word_index(story: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    words = story.get("words", story.get("lexicon", []))
    result: Dict[str, Dict[str, Any]] = {}
    if isinstance(words, dict):
        words = list(words.values())
    for entry in words:
        identity = str(entry.get("word", entry.get("identity", ""))).upper()
        if identity:
            result[identity] = entry
    return result

def process_text(root: Path, text: str, *, observer: str, environment: str, sector: str, service: str, emit_receipt: bool=False) -> Dict[str, Any]:
    root = root.resolve(); registry = load_registry(root); story = load_active_story(root); index = word_index(story)
    tokens = TOKEN_RE.findall(text)
    resolved, unresolved = [], []
    concepts = registry["canonicalConcepts"]
    for token in tokens:
        key = token.upper(); lower = token.lower()
        if key in index:
            resolved.append({"term":token,"source":"active-story","canonical":index[key].get("address", index[key].get("canonical_id", f"word://{lower}"))})
        elif lower in concepts:
            resolved.append({"term":token,"source":"il-llm-registry","canonical":f"concept://{concepts[lower]['concept'].lower()}","role":concepts[lower]["role"]})
        else:
            unresolved.append(token)
    expression = {
        "address": f"expression://il-llm/{canonical_hash({'text':text,'sector':sector,'service':service})[:16]}",
        "text": text,
        "tokens": tokens,
        "resolved_terms": resolved,
        "unresolved_terms": unresolved,
        "observer": observer,
        "environment": environment,
        "sector": sector,
        "service": service,
        "transition": registry["canonicalTransition"],
        "source_preserved": True,
        "complete_context": 1,
    }
    state = "CONTEXTUALIZED" if not unresolved else "LEARNING_REQUIRED"
    receipt = {
        "version":"V101-ILLLM-1","expression":expression,"state":state,
        "global_stop":False,"continuation":"RETURN" if not unresolved else "MIRROR_UNRESOLVED_TERMS",
        "timestamp":time.time(),
    }
    receipt["receipt_id"] = canonical_hash(receipt)
    ledger = root / "runtime_volume" / "il_llm_story.ledger"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle: handle.write(json.dumps(receipt, sort_keys=True)+"\n")
    if unresolved:
        write_json(root / "runtime_volume" / "workplans" / "il_llm_learning" / f"{receipt['receipt_id']}.json", {
            "blocked_capability":"canonical term resolution","blocked_domain":"service://il-llm-lexicon-resolution","criticality":"CORE_DEGRADED",
            "root_cause":"unresolved complete word identities","unresolved_terms":unresolved,"source_text":text,
            "continuation_mode":"preserve expression and stage mirror learning","unaffected_domains":["active-story runtime","known-word resolution"],
            "reentry_conditions":["canonical definitions added","source lineage attached","expression reprocessed"],"global_stop":False
        })
    if emit_receipt: write_json(root / "evidence" / "il_llm_context_receipt.json", receipt)
    return receipt

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--root",default="."); p.add_argument("--text",required=True); p.add_argument("--observer",default="operator"); p.add_argument("--environment",default="BRAINK"); p.add_argument("--sector",default="sector://learning-and-knowledge"); p.add_argument("--service",default="service://il-llm-context-integration"); p.add_argument("--emit-receipt",action="store_true"); a=p.parse_args()
    result=process_text(Path(a.root),a.text,observer=a.observer,environment=a.environment,sector=a.sector,service=a.service,emit_receipt=a.emit_receipt); print(json.dumps(result,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
