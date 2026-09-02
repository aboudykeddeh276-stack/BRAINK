#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes


WEIGHTS = {
    "dependencyImpact": 3,
    "evidenceDeficit": 3,
    "downstreamUnlock": 2,
    "executionFeasibility": 2,
    "criticality": 2,
    "alreadyClosed": -4,
}


def score(candidate: dict[str, Any]) -> int:
    return sum(int(candidate.get(field, 0)) * weight for field, weight in WEIGHTS.items())


def select(queue: dict[str, Any]) -> dict[str, Any]:
    candidates = [dict(item) for item in queue.get("candidates", [])]
    if not candidates:
        raise ValueError("execution queue has no candidates")
    for item in candidates:
        item["score"] = score(item)
    candidates.sort(key=lambda item: (-item["score"], int(item.get("ordinal", 10**9)), str(item.get("taskId", ""))))
    selected = candidates[0]
    queue_hash = sha256_bytes(canonical_json_bytes(queue))
    receipt = {
        "schema": "kex.illlm.execution-selection.v1",
        "queueHash": queue_hash,
        "weights": WEIGHTS,
        "selectedTaskId": selected["taskId"],
        "selectedScore": selected["score"],
        "selectedAction": selected["action"],
        "promotionEvidence": selected.get("promotionEvidence"),
        "ranking": [
            {"taskId": item["taskId"], "score": item["score"], "ordinal": item.get("ordinal")}
            for item in candidates
        ],
        "claimBoundary": "This receipt proves deterministic selection from the supplied accumulated-state queue. It does not prove execution or completion of the selected task.",
    }
    receipt["selectionHash"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def run(queue_path: Path, output_path: Path) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    receipt = select(queue)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[2]
    receipt = run(
        base / "runtime" / "ILLLM_EXECUTION_QUEUE_R1.json",
        base / "runtime" / "ILLLM_EXECUTION_SELECTION_R1.json",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
