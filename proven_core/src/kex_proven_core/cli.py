from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import Mutation, PromotionGate, build_minframe


def main() -> int:
    parser = argparse.ArgumentParser(prog="kex-proven-core")
    parser.add_argument("--state-dir", default=".kex-proven-state")
    parser.add_argument("--public-proof", action="append", default=[])
    args = parser.parse_args()

    registry, ledger, admission = build_minframe()
    identity = "app://kex/active-state"
    base = admission.seed(identity, {"boot": "MINFRAME_R1", "status": "LOCAL"})
    admitted = admission.admit(Mutation(
        actor="braink://local/orchestrator",
        subject=identity,
        operation="BOOT",
        expected_canonical_key=identity,
        payload={"projection": "projection://braink/local"},
        base_state_hash=base,
    ))
    provided = {name: name in set(args.public_proof) for name in PromotionGate.REQUIRED_PUBLIC}
    promotion = PromotionGate(ledger).evaluate("volume://keddeh/braink/root", provided)

    out = Path(args.state_dir)
    out.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema": "kex.proven-core.minframe.r1",
        "registry": [item.__dict__ | {"surface": item.surface.value} for item in registry.snapshot()],
        "ledger_root": ledger.root,
        "ledger_valid": ledger.verify(),
        "receipts": [item.__dict__ | {"state": item.state.value} for item in ledger.receipts],
        "promotion_state": "PUBLIC_LIVE" if promotion.state.value == "PUBLIC_READBACK" else "STAGED_NOT_PUBLIC_LIVE",
    }
    (out / "runtime-state.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"boot_receipt": admitted.receipt_id, "ledger_root": ledger.root, "promotion_state": snapshot["promotion_state"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
