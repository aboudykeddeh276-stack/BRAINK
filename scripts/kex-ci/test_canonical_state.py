#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from modules.kex_core.canonical_state import CanonicalBoundary, WrapperAdapter, json_adapter, mapping_adapter


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    boundary = CanonicalBoundary()
    boundary.register(json_adapter("json"))
    boundary.register(mapping_adapter("vfs"))
    boundary.register(mapping_adapter("runtime"))

    source = {
        "identity": "KEX.TEST.1",
        "value": 1,
        "nested": {"resonance": 0.297, "axis": [-3, -2, 1, 2, 3]},
    }

    state, vfs_state = boundary.traverse(
        "json",
        "vfs",
        json.dumps(source),
        identity="KEX.TEST.1",
        authority="A.KEDDEH",
        dependency_hops=2,
        fan_out=3,
    )
    require(vfs_state == source, "JSON -> canonical -> VFS changed semantic state")
    require(state.identity == "KEX.TEST.1", "canonical identity was not preserved")
    require(state.lineage[-1] == "wrapper://json", "source wrapper lineage missing")

    runtime_state = boundary.exit("runtime", state, dependency_hops=1, fan_out=2)
    require(runtime_state == source, "canonical -> runtime changed semantic state")

    envelope = state.envelope()
    require(envelope["schema"] == "kex.canonical-state.v1", "canonical schema mismatch")
    require(envelope["evidenceLevel"] == "SOFTWARE_OBSERVED", "evidence class over-promoted")
    require(len(envelope["stateDigest"]) == 64, "state digest missing")

    metrics = boundary.metrics()
    require(metrics["crossings"] == 3, "crossing count incorrect")
    require(metrics["totalPropagationCost"] > 0, "propagation cost was not measured")
    require(metrics["peakSignalDensity"] > 0, "signal density was not measured")

    lossy = CanonicalBoundary()
    lossy.register(
        WrapperAdapter(
            name="lossy",
            ingress=lambda raw: dict(raw),
            egress=lambda payload: {"identity": payload.get("identity")},
        )
    )
    lossy_state = lossy.enter(
        "lossy",
        source,
        identity="KEX.TEST.1",
        authority="A.KEDDEH",
    )
    detected = False
    try:
        lossy.exit("lossy", lossy_state)
    except ValueError:
        detected = True
    require(detected, "lossy wrapper crossing was not rejected")

    receipt = {
        "schema": "kex.canonical-state-test.v1",
        "state": "PASS",
        "canonicalization": "wrapper -> canonical -> wrapper",
        "identityPreserved": True,
        "lossDetection": "PASS",
        "metrics": metrics,
        "claimBoundary": (
            "This proves deterministic software canonicalization, wrapper round-trip "
            "identity checking, lineage capture, and software propagation instrumentation "
            "for this execution. It does not prove processor, electrical, thermal, ASIC, "
            "or physical-memory performance improvements."
        ),
    }
    out = ROOT / "reports" / "kex-core" / "canonical-state-test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
