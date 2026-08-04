#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def unique_append(mapping: Dict[str, List[str]], key: str, value: str) -> None:
    mapping.setdefault(key, [])
    if value not in mapping[key]:
        mapping[key].append(value)


class ActiveWordFullEngagement:
    """Iteratively engages every registered active word and returns derivations bilaterally."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.policy = read_json(self.root / "config" / "active_word_full_engagement.json")
        self.story = read_json(self.root / "config" / "active_story_lexicon.json")
        self.word_policy = read_json(self.root / "config" / "active_word_governance.json")
        self.il_llm = read_json(self.root / "config" / "il_llm_active_story_registry.json")
        self.words = {word["id"]: word for word in self.story["words"]}
        self.expressions = {expr["id"]: expr for expr in self.story["expressions"]}
        self.runtime_dir = self.root / "runtime_volume" / "active_word_full_engagement"
        self.ledger = self.runtime_dir / "engagement_ledger.jsonl"
        self.proposals_dir = self.root / "runtime_volume" / "workplans" / "active_word_mirror_lane"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.policy.get("canonicalEquation") != "A_W=f(W,C,E,S,V,O,L,T)":
            errors.append("invalid_active_word_equation")
        if self.il_llm.get("wordModel") != "(- WORD +)":
            errors.append("missing_il_llm_word_model")
        if self.policy.get("iterations", 0) < 1:
            errors.append("iterations_must_be_positive")
        for expr_id, expr in self.expressions.items():
            for item in expr.get("words", []):
                if item.get("word") not in self.words:
                    errors.append(f"{expr_id}:unknown_word:{item.get('word')}")
        return errors

    def _proposal(self, kind: str, subject: str, source_addresses: List[str], detail: Dict[str, Any]) -> Dict[str, Any]:
        proposal = {
            "proposal_id": "proposal://mirror-lane/" + canonical_hash({"kind": kind, "subject": subject, "sources": source_addresses, "detail": detail}),
            "kind": kind,
            "subject": subject,
            "source_addresses": source_addresses,
            "detail": detail,
            "state": "PROPOSED_UPDATE",
            "required_path": ["MIRRORED", "VALIDATED", "REINTEGRATED"],
            "global_stop": False,
            "created_at": time.time(),
        }
        write_json(self.proposals_dir / f"{proposal['proposal_id'].rsplit('/',1)[-1]}.json", proposal)
        return proposal

    def _derivation(self, kind: str, left: str, right: str, basis: Dict[str, Any], iteration: int) -> Dict[str, Any]:
        body = {
            "kind": kind,
            "left": left,
            "right": right,
            "basis": basis,
            "iteration": iteration,
            "complete": 1,
            "preserved": True,
        }
        body["derivation_id"] = "derivation://active-word/" + canonical_hash(body)
        return body

    def _engage_expression(self, expr_id: str, expr: Dict[str, Any], iteration: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        derivations: List[Dict[str, Any]] = []
        proposals: List[Dict[str, Any]] = []
        service = expr.get("service")
        sector = expr.get("sector")
        handler = expr.get("handler")
        evidence = expr.get("requiredEvidence", [])
        words = [item.get("word") for item in expr.get("words", [])]

        if not service or not sector or not handler:
            proposals.append(self._proposal(
                "MISSING_EXPRESSION_BINDING",
                expr_id,
                [expr_id] + [w for w in words if w],
                {"service": service, "sector": sector, "handler": handler},
            ))

        for word_id in words:
            if not word_id:
                continue
            derivations.extend([
                self._derivation("WORD_TO_EXPRESSION", word_id, expr_id, {"role": next((x.get("role") for x in expr["words"] if x.get("word") == word_id), "unspecified")}, iteration),
                self._derivation("WORD_TO_SECTOR", word_id, sector, {"expression": expr_id}, iteration),
                self._derivation("WORD_TO_EVIDENCE", word_id, expr_id, {"required_evidence": evidence}, iteration),
            ])
        if service:
            derivations.append(self._derivation("EXPRESSION_TO_SERVICE", expr_id, service, {"sector": sector}, iteration))
        if handler:
            derivations.append(self._derivation("SERVICE_TO_HANDLER", service or "service://unresolved", handler, {"expression": expr_id}, iteration))
        return derivations, proposals

    def _emergent_relations(self, iteration: int) -> List[Dict[str, Any]]:
        relations: List[Dict[str, Any]] = []
        word_items = list(self.words.items())
        for index, (left_id, left) in enumerate(word_items):
            left_invariants = set(left.get("invariants", []))
            left_variants = set(left.get("variants", []))
            for right_id, right in word_items[index + 1:]:
                shared_invariants = sorted(left_invariants.intersection(right.get("invariants", [])))
                shared_variants = sorted(left_variants.intersection(right.get("variants", [])))
                if shared_invariants:
                    relations.append(self._derivation("SHARED_INVARIANT", left_id, right_id, {"invariants": shared_invariants}, iteration))
                if shared_variants:
                    relations.append(self._derivation("SHARED_DEPENDENCY", left_id, right_id, {"contextual_variants": shared_variants}, iteration))
        return relations

    def run(self, iterations: Optional[int] = None, emit_receipt: bool = False) -> Dict[str, Any]:
        errors = self.validate()
        if errors:
            return {"promotion_state": "CONTEXT_RESOLUTION_REQUIRED", "errors": errors, "global_stop": False}

        iteration_count = iterations or int(self.policy["iterations"])
        all_derivations: Dict[str, Dict[str, Any]] = {}
        all_proposals: Dict[str, Dict[str, Any]] = {}
        indexes: Dict[str, Dict[str, List[str]]] = {
            name: {} for name in self.policy["requiredBilateralIndexes"]
        }
        iteration_receipts: List[Dict[str, Any]] = []

        for iteration in range(1, iteration_count + 1):
            before = len(all_derivations)
            for expr_id, expr in self.expressions.items():
                derivations, proposals = self._engage_expression(expr_id, expr, iteration)
                for derivation in derivations:
                    all_derivations.setdefault(derivation["derivation_id"], derivation)
                for proposal in proposals:
                    all_proposals.setdefault(proposal["proposal_id"], proposal)
            for derivation in self._emergent_relations(iteration):
                all_derivations.setdefault(derivation["derivation_id"], derivation)

            for derivation in all_derivations.values():
                left, right, kind, did = derivation["left"], derivation["right"], derivation["kind"], derivation["derivation_id"]
                unique_append(indexes["forward"], left, did)
                unique_append(indexes["reverse"], right, did)
                if kind == "WORD_TO_EXPRESSION":
                    unique_append(indexes["word_to_expression"], left, right)
                    unique_append(indexes["expression_to_word"], right, left)
                if kind == "EXPRESSION_TO_SERVICE":
                    unique_append(indexes["service_to_transition"], right, left)
                    unique_append(indexes["transition_to_service"], left, right)
                unique_append(indexes["source_to_runtime"], left, right)
                unique_append(indexes["runtime_to_source"], right, left)

            added = len(all_derivations) - before
            receipt = {
                "iteration": iteration,
                "phase_sequence": self.policy["phases"],
                "derivations_total": len(all_derivations),
                "new_derivations": added,
                "proposals_total": len(all_proposals),
                "converged": added == 0,
                "global_stop": False,
                "timestamp": time.time(),
            }
            iteration_receipts.append(receipt)
            append_jsonl(self.ledger, receipt)
            if added == 0:
                break

        derivation_list = sorted(all_derivations.values(), key=lambda item: item["derivation_id"])
        proposal_list = sorted(all_proposals.values(), key=lambda item: item["proposal_id"])
        for derivation in derivation_list:
            append_jsonl(self.runtime_dir / "derivations.jsonl", derivation)
        for name, mapping in indexes.items():
            write_json(self.runtime_dir / "indexes" / f"{name}.json", mapping)

        bilateral_ok = True
        for word, expressions in indexes["word_to_expression"].items():
            for expression in expressions:
                if word not in indexes["expression_to_word"].get(expression, []):
                    bilateral_ok = False
        for expression, services in indexes["transition_to_service"].items():
            for service in services:
                if expression not in indexes["service_to_transition"].get(service, []):
                    bilateral_ok = False

        receipt = {
            "version": self.policy["version"],
            "words_engaged": len(self.words),
            "expressions_engaged": len(self.expressions),
            "iterations_executed": len(iteration_receipts),
            "iteration_receipts": iteration_receipts,
            "derivations_preserved": len(derivation_list),
            "mirror_lane_proposals": len(proposal_list),
            "bilateral_readback": bilateral_ok,
            "indexes_written": sorted(indexes),
            "promotion_state": "REINTEGRATED" if bilateral_ok else "BILATERAL_RECONCILIATION_REQUIRED",
            "global_stop": False,
            "timestamp": time.time(),
        }
        receipt["receipt_id"] = "receipt://active-word-full-engagement/" + canonical_hash(receipt)
        if emit_receipt:
            write_json(self.root / "evidence" / "active_word_full_engagement_receipt.json", receipt)
        return receipt


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = ActiveWordFullEngagement(Path(args.root)).run(args.iterations, args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("bilateral_readback") else 1


if __name__ == "__main__":
    raise SystemExit(main())
