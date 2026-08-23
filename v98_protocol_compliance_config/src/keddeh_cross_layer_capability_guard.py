#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class GuardDecision:
    guard_id: str
    requested_decision: str
    permitted: bool
    state: str
    reason: str
    traversed_layers: int
    required_layers: int
    reusable_layers: List[str]
    concurrency_preserved: bool


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_policy(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "cross_layer_capability_guard.json")


def validate_traversal(policy: Dict[str, Any], traversal: Any) -> tuple[bool, str, Dict[str, Dict[str, Any]]]:
    if not isinstance(traversal, list):
        return False, "traversal_must_be_array", {}
    required = list(policy["required_layers"])
    required_set = set(required)
    allowed_states = set(policy["allowed_result_states"])
    seen: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(traversal):
        if not isinstance(row, dict):
            return False, f"record_{index}_not_object", {}
        for field in policy["required_traversal_fields"]:
            if field not in row:
                return False, f"record_{index}_missing_{field}", {}
        layer = str(row["layer_id"])
        if layer not in required_set:
            return False, f"unknown_layer_{layer}", {}
        if layer in seen:
            return False, f"duplicate_layer_{layer}", {}
        if not str(row["search_scope"]).strip():
            return False, f"empty_search_scope_{layer}", {}
        evidence = row["evidence_paths"]
        if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
            return False, f"missing_evidence_paths_{layer}", {}
        mechanics = row["mechanics_found"]
        if not isinstance(mechanics, list):
            return False, f"mechanics_found_not_array_{layer}", {}
        state = str(row["result_state"])
        if state not in allowed_states:
            return False, f"invalid_result_state_{layer}", {}
        if state == "NO_MATCH_WITH_EVIDENCE" and mechanics:
            return False, f"no_match_contains_mechanics_{layer}", {}
        if state != "NO_MATCH_WITH_EVIDENCE" and not mechanics:
            return False, f"positive_result_without_mechanics_{layer}", {}
        seen[layer] = row
    missing = [layer for layer in required if layer not in seen]
    if missing:
        return False, "missing_layers:" + ",".join(missing), seen
    return True, "complete", seen


def evaluate(root: Path, traversal: Any, requested_decision: str) -> GuardDecision:
    policy = load_policy(root)
    protected = set(policy["protected_decisions"])
    valid, reason, seen = validate_traversal(policy, traversal)
    required_count = len(policy["required_layers"])
    if requested_decision not in protected:
        return GuardDecision(policy["guard_id"], requested_decision, True, "OUTSIDE_PROTECTED_DECISION_SET", "decision_not_guarded", len(seen), required_count, [], True)
    if not valid:
        return GuardDecision(policy["guard_id"], requested_decision, False, "TRAVERSAL_INCOMPLETE", reason, len(seen), required_count, [], False)

    reusable_states = {"FOUND_REUSE", "FOUND_ADAPT", "FOUND_BRIDGE"}
    reusable_layers = [layer for layer, row in seen.items() if row["result_state"] in reusable_states]
    kex = seen["KEX_MATHEMATICS_AND_CONCURRENCY"]
    concurrency_found = bool(kex["mechanics_found"]) and kex["result_state"] in reusable_states

    if requested_decision == "SEQUENTIALIZE_CONCURRENT_MECHANIC" and concurrency_found:
        return GuardDecision(policy["guard_id"], requested_decision, False, "REUSE_REQUIRED", "kex_concurrency_mechanic_exists", len(seen), required_count, reusable_layers, True)

    if requested_decision in {"DERIVE_REPLACEMENT", "SUBSTITUTE_ARCHITECTURE"} and reusable_layers:
        return GuardDecision(policy["guard_id"], requested_decision, False, "REUSE_REQUIRED", "existing_reuse_adapt_or_bridge_path_exists", len(seen), required_count, reusable_layers, concurrency_found)

    if requested_decision in {"CAPABILITY_MISSING", "CAPABILITY_LIMITATION"}:
        non_exhausted = [layer for layer, row in seen.items() if row["result_state"] != "NO_MATCH_WITH_EVIDENCE"]
        if non_exhausted:
            return GuardDecision(policy["guard_id"], requested_decision, False, "REUSE_REQUIRED", "one_or_more_layers_contain_existing_mechanics", len(seen), required_count, non_exhausted, concurrency_found)
        return GuardDecision(policy["guard_id"], requested_decision, True, "ALL_LAYERS_EXHAUSTED", "negative_claim_eligible_but_requires_independent_evidence_review", len(seen), required_count, [], concurrency_found)

    return GuardDecision(policy["guard_id"], requested_decision, False, "FAIL_CLOSED", "protected_decision_not_explicitly_resolved", len(seen), required_count, reusable_layers, concurrency_found)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--traversal", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    traversal = read_json(Path(args.traversal).expanduser().resolve())
    decision = evaluate(root, traversal, args.decision)
    payload = {"decision": asdict(decision), "stage": "STAGE_1_FAIL_CLOSED_TRAVERSAL"}
    if args.emit_receipt:
        write_json(root / "evidence" / "cross_layer_capability_guard_receipt.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if decision.permitted else 3


if __name__ == "__main__":
    raise SystemExit(main())
