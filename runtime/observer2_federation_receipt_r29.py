from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from braink_observer2_bootstrap_r29 import build_observer2_federation
from braink_recursive_operator_r29 import RecursiveObserverOperator
from observer2_federation_r29 import Observer2Runtime


def build_receipt(*, repository: str | None = None, machine_disk: str | None = None,
                  public_edge_url: str | None = None, include_process: bool = True,
                  objective: str = "observe-environment-federation",
                  recommendation: str = "reconcile-before-actuation") -> Mapping[str, Any]:
    federation = build_observer2_federation(
        repository=repository,
        machine_disk=machine_disk,
        public_edge_url=public_edge_url,
        include_process=include_process,
    )
    operator = RecursiveObserverOperator(Observer2Runtime(federation=federation))
    cycle = operator.cycle(
        objective=objective,
        recommendation=recommendation,
        continuation={"source": "observer2_federation_receipt_r29"},
    )
    statuses = [r["status"] for r in cycle["frame"]["receipts"]]
    if statuses and all(s == "OBSERVED" for s in statuses):
        classification = "OBSERVED"
    elif any(s == "OBSERVED" for s in statuses):
        classification = "MIXED_OBSERVED_AND_UNAVAILABLE"
    else:
        classification = "UNAVAILABLE"
    return {
        "schema": "kex.observer2.federation-execution-receipt.r29",
        "classification": classification,
        "authority": "EVIDENCE_ONLY_NO_ACTUATION",
        "cycle": cycle,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate an Observer² federated environment receipt")
    ap.add_argument("--repository")
    ap.add_argument("--machine-disk")
    ap.add_argument("--public-edge-url")
    ap.add_argument("--no-process", action="store_true")
    ap.add_argument("--objective", default="observe-environment-federation")
    ap.add_argument("--recommendation", default="reconcile-before-actuation")
    ap.add_argument("--out", required=True)
    ns = ap.parse_args()
    receipt = build_receipt(
        repository=ns.repository,
        machine_disk=ns.machine_disk,
        public_edge_url=ns.public_edge_url,
        include_process=not ns.no_process,
        objective=ns.objective,
        recommendation=ns.recommendation,
    )
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "classification": receipt["classification"],
        "environment_root_sha256": receipt["cycle"]["frame"]["environment_root_sha256"],
        "receipt": str(out),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
