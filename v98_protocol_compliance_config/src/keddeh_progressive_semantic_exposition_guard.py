#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ExpositionDecision:
    guard_id: str
    valid: bool
    state: str
    reason: str
    completed_stages: List[str]
    missing_stages: List[str]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy(root: Path) -> Dict[str, Any]:
    return read_json(root / "config" / "progressive_semantic_exposition_guard.json")


def evaluate(root: Path, exposition: Any) -> ExpositionDecision:
    policy = load_policy(root)
    required = list(policy["required_progression"])
    if not isinstance(exposition, dict):
        return ExpositionDecision(policy["guard_id"], False, "UNEXPANDED_ABSTRACTION", "exposition_must_be_object", [], required)

    completed: List[str] = []
    missing: List[str] = []
    for stage in required:
        value = exposition.get(stage)
        if isinstance(value, str) and value.strip():
            completed.append(stage)
        else:
            missing.append(stage)

    if missing:
        return ExpositionDecision(policy["guard_id"], False, "UNEXPANDED_ABSTRACTION", "missing_required_progression_stage", completed, missing)

    term = exposition["TECHNICAL_TERM"].strip()
    plain = exposition["PLAIN_ENGLISH_MEANING"].strip()
    analogy = exposition["FAMILIAR_ANALOGY"].strip()
    simpler = exposition["SIMPLER_PROCESS_OR_PHYSICAL_ANALOGY"].strip()
    primitive = exposition["PRIMITIVE_OPERATION"].strip()
    binding = exposition["SYSTEM_SPECIFIC_BINDING"].strip()

    if term == plain or term == analogy or term == simpler:
        return ExpositionDecision(policy["guard_id"], False, "JARGON_RECURSION", "technical_term_repeated_without_decompression", completed, [])
    if len(primitive.split()) < 4:
        return ExpositionDecision(policy["guard_id"], False, "ANALOGY_WITHOUT_PRIMITIVE", "primitive_operation_not_explicit_enough", completed, [])
    if term.lower() not in binding.lower() and not any(token.lower() in binding.lower() for token in term.replace("/", " ").split() if len(token) > 3):
        return ExpositionDecision(policy["guard_id"], False, "PRIMITIVE_NOT_BOUND_TO_SYSTEM", "system_binding_does_not_reference_the_grounded_concept", completed, [])

    return ExpositionDecision(policy["guard_id"], True, "CONTEXTUALLY_GROUNDED", "all_required_progression_stages_present", completed, [])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--exposition", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    decision = evaluate(root, read_json(Path(args.exposition).expanduser().resolve()))
    print(json.dumps({"decision": asdict(decision)}, indent=2, sort_keys=True))
    return 0 if decision.valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
