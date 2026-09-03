from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

EVIDENCE_LEVELS = {
    0: "CONCEPT_STATED",
    1: "FORMALISED",
    2: "IMPLEMENTATION_EXISTS",
    3: "EXECUTES",
    4: "ISOLATED_QUALIFIED",
    5: "INTEGRATION_QUALIFIED",
    6: "ADVERSARIAL_QUALIFIED",
    7: "RESTART_PERSISTENCE_QUALIFIED",
    8: "CROSS_PROCESS_QUALIFIED",
    9: "CROSS_MACHINE_QUALIFIED",
    10: "EXTERNAL_INTEROPERABILITY_QUALIFIED",
    11: "REPEATABILITY_ESTABLISHED",
    12: "COMPARATIVE_BENCHMARK_ESTABLISHED",
}

TERMINAL_STATUSES = {"PASS", "FAIL", "BLOCKED", "EXECUTOR_UNAVAILABLE"}


@dataclass(frozen=True)
class Executor:
    executor_id: str
    kind: str
    capabilities: tuple[str, ...]
    available: bool


@dataclass(frozen=True)
class Receipt:
    claim_id: str
    proof_id: str
    executor_id: str
    status: str
    evidence_level: int
    observation: str
    artifact: str | None = None

    def validate(self) -> None:
        if self.status not in TERMINAL_STATUSES:
            raise ValueError(f"invalid receipt status: {self.status}")
        if self.evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"invalid evidence level: {self.evidence_level}")
        if not self.observation.strip():
            raise ValueError("receipt observation must not be empty")


def select_executor(required_capabilities: list[str], executors: list[Executor]) -> Executor | None:
    required = set(required_capabilities)
    candidates = [e for e in executors if e.available and required.issubset(set(e.capabilities))]
    return sorted(candidates, key=lambda e: (len(e.capabilities), e.executor_id))[0] if candidates else None


def reconcile(claim: dict[str, Any], receipts: list[Receipt]) -> dict[str, Any]:
    claim_id = claim["claim_id"]
    relevant = [r for r in receipts if r.claim_id == claim_id]
    for r in relevant:
        r.validate()

    by_proof: dict[str, list[Receipt]] = {}
    for r in relevant:
        by_proof.setdefault(r.proof_id, []).append(r)

    proof_results: list[dict[str, Any]] = []
    all_required_pass = True
    highest_observed = 0
    any_fail = False
    any_blocked = False

    for req in claim["proof_requirements"]:
        proof_id = req["proof_id"]
        minimum = int(req["minimum_level"])
        observed = by_proof.get(proof_id, [])
        passing = [r for r in observed if r.status == "PASS" and r.evidence_level >= minimum]
        failing = [r for r in observed if r.status == "FAIL"]
        blocked = [r for r in observed if r.status in {"BLOCKED", "EXECUTOR_UNAVAILABLE"}]
        if observed:
            highest_observed = max(highest_observed, max(r.evidence_level for r in observed))
        satisfied = bool(passing) and not failing
        all_required_pass = all_required_pass and satisfied
        any_fail = any_fail or bool(failing)
        any_blocked = any_blocked or (not satisfied and bool(blocked))
        proof_results.append(
            {
                "proof_id": proof_id,
                "minimum_level": minimum,
                "satisfied": satisfied,
                "receipts": [asdict(r) for r in observed],
            }
        )

    required_level = int(claim["required_evidence_level"])
    if any_fail:
        conclusion = "REJECTED"
    elif all_required_pass and highest_observed >= required_level:
        conclusion = "SUPPORTED"
    elif any_blocked:
        conclusion = "BLOCKED"
    elif relevant:
        conclusion = "PARTIALLY_SUPPORTED"
    else:
        conclusion = "UNEXECUTED"

    return {
        "schema": "braink.kex.research-reconciliation.v1",
        "claim_id": claim_id,
        "conclusion": conclusion,
        "required_evidence_level": required_level,
        "highest_observed_evidence_level": highest_observed,
        "highest_observed_evidence_label": EVIDENCE_LEVELS[highest_observed],
        "proof_results": proof_results,
        "promotion_allowed": conclusion == "SUPPORTED",
        "invalid_overclaims": claim["invalid_overclaims"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claim", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    claim = json.loads(args.claim.read_text("utf-8"))
    raw = json.loads(args.receipts.read_text("utf-8"))
    receipts = [Receipt(**item) for item in raw]
    result = reconcile(claim, receipts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps({"claim_id": result["claim_id"], "conclusion": result["conclusion"], "promotion_allowed": result["promotion_allowed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
