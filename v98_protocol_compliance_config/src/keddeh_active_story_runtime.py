#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class SemanticBinding:
    word: str
    expression: str
    sector: str
    service: str
    handler: str


@dataclass(frozen=True)
class StoryTransition:
    transition_id: str
    expression_id: str
    sector: str
    service: str
    subject: str
    prior_state: str
    next_state: str
    observer: str
    environment: str
    execution_plane: str
    evidence_class: str
    evidence: Dict[str, Any]
    source_words: List[str]
    timestamp: float


def canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


class ActiveStoryRuntime:
    """Executable encyclopedia of source-linked contextual state transitions."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.registry_path = self.root / "config" / "active_story_lexicon.json"
        self.registry = read_json(self.registry_path)
        self.words = {entry["id"]: entry for entry in self.registry["words"]}
        self.expressions = {entry["id"]: entry for entry in self.registry["expressions"]}
        self.story_dir = self.root / "runtime_volume" / "active_story"
        self.ledger_path = self.story_dir / "transition_ledger.jsonl"
        self.backlinks_path = self.story_dir / "backlinks.json"

    def validate_registry(self) -> List[str]:
        errors: List[str] = []
        for word_id, word in self.words.items():
            for field in ("term", "definition", "invariants", "variants"):
                if not word.get(field):
                    errors.append(f"{word_id}:missing:{field}")
        for expression_id, expression in self.expressions.items():
            if not expression.get("words"):
                errors.append(f"{expression_id}:missing:words")
            for item in expression.get("words", []):
                if item.get("word") not in self.words:
                    errors.append(f"{expression_id}:unknown_word:{item.get('word')}")
            for field in ("sector", "service", "definition", "handler", "requiredEvidence"):
                if not expression.get(field):
                    errors.append(f"{expression_id}:missing:{field}")
        return errors

    def definition(self, word_id: str) -> Dict[str, Any]:
        if word_id not in self.words:
            raise KeyError(f"unknown_word:{word_id}")
        return self.words[word_id]

    def compose_expression(self, expression_id: str) -> Dict[str, Any]:
        if expression_id not in self.expressions:
            raise KeyError(f"unknown_expression:{expression_id}")
        expression = dict(self.expressions[expression_id])
        expression["sourceDefinitions"] = {
            item["word"]: self.definition(item["word"])["definition"]
            for item in expression["words"]
        }
        expression["sourceInvariants"] = {
            item["word"]: self.definition(item["word"])["invariants"]
            for item in expression["words"]
        }
        return expression

    def semantic_binding(self, expression_id: str) -> SemanticBinding:
        expression = self.compose_expression(expression_id)
        return SemanticBinding(
            word=expression["words"][0]["word"],
            expression=expression_id,
            sector=expression["sector"],
            service=expression["service"],
            handler=expression["handler"],
        )

    def _validate_evidence(self, expression: Dict[str, Any], evidence: Dict[str, Any]) -> List[str]:
        return [field for field in expression["requiredEvidence"] if field not in evidence]

    def transition(
        self,
        expression_id: str,
        subject: str,
        prior_state: str,
        next_state: str,
        observer: str,
        environment: str,
        execution_plane: str,
        evidence_class: str,
        evidence: Dict[str, Any],
        emit_receipt: bool = True,
    ) -> Dict[str, Any]:
        expression = self.compose_expression(expression_id)
        missing = self._validate_evidence(expression, evidence)
        if missing:
            return {
                "promotion_state": "EVIDENCE_CORRELATION_REQUIRED",
                "global_stop": False,
                "expression_id": expression_id,
                "subject": subject,
                "missing_evidence": missing,
                "capability_effect": f"hold only {expression['service']} transition",
            }
        timestamp = time.time()
        source_words = [item["word"] for item in expression["words"]]
        seed = {
            "expression_id": expression_id,
            "subject": subject,
            "prior_state": prior_state,
            "next_state": next_state,
            "observer": observer,
            "environment": environment,
            "execution_plane": execution_plane,
            "evidence_class": evidence_class,
            "evidence": evidence,
            "timestamp": timestamp,
        }
        transition_hash = hashlib.sha256(canonical_bytes(seed)).hexdigest()
        transition = StoryTransition(
            transition_id=f"story://{expression['sector'].split('://',1)[-1]}/{transition_hash}",
            expression_id=expression_id,
            sector=expression["sector"],
            service=expression["service"],
            subject=subject,
            prior_state=prior_state,
            next_state=next_state,
            observer=observer,
            environment=environment,
            execution_plane=execution_plane,
            evidence_class=evidence_class,
            evidence=evidence,
            source_words=source_words,
            timestamp=timestamp,
        )
        payload = asdict(transition)
        append_jsonl(self.ledger_path, payload)
        backlinks = read_json(self.backlinks_path) if self.backlinks_path.exists() else {}
        for address in source_words + [expression_id, expression["sector"], expression["service"]]:
            backlinks.setdefault(address, [])
            if transition.transition_id not in backlinks[address]:
                backlinks[address].append(transition.transition_id)
        write_json(self.backlinks_path, backlinks)
        receipt_path = self.story_dir / "receipts" / f"{transition_hash}.json"
        receipt = {
            "transition": payload,
            "expression": expression,
            "binding": asdict(self.semantic_binding(expression_id)),
            "receipt_uri": f"receipt://active-story/{transition_hash}",
            "ledger_readback": any(
                json.loads(line).get("transition_id") == transition.transition_id
                for line in self.ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ),
            "promotion_state": "LOCAL_PASS",
        }
        if emit_receipt:
            write_json(receipt_path, receipt)
        return receipt

    def backlink(self, address: str) -> List[str]:
        if not self.backlinks_path.exists():
            return []
        return read_json(self.backlinks_path).get(address, [])

    def build_index(self) -> Dict[str, Any]:
        errors = self.validate_registry()
        index = {
            "version": self.registry["version"],
            "registry_id": self.registry["registryId"],
            "word_count": len(self.words),
            "expression_count": len(self.expressions),
            "registry_valid": not errors,
            "errors": errors,
            "words": sorted(self.words),
            "expressions": sorted(self.expressions),
            "story_rule": "every execution links to source words, expression, sector, service, observer, environment, evidence and lineage",
        }
        write_json(self.story_dir / "index.json", index)
        return index


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    parser.add_argument("--expression", default="expression://verify-manifest-before-node-execution")
    args = parser.parse_args(argv)
    runtime = ActiveStoryRuntime(Path(args.root))
    index = runtime.build_index()
    result = runtime.transition(
        args.expression,
        subject="kex.workstation.core",
        prior_state="PACKAGED",
        next_state="INTEGRITY_VERIFIED",
        observer="service://k-cloud-admission",
        environment="environment://portable-ci",
        execution_plane="CONTROL_PLANE",
        evidence_class="RECEIPT_BACKED",
        evidence={
            "manifest_hash_expected": "fixture-expected",
            "manifest_hash_actual": "fixture-expected",
            "node_execution_allowed": True,
        },
        emit_receipt=args.emit_receipt,
    )
    print(json.dumps({"index": index, "transition": result}, indent=2, sort_keys=True))
    return 0 if index["registry_valid"] and result.get("promotion_state") == "LOCAL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
