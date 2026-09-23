from __future__ import annotations

import json
import platform
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.evolution_control_plane_r25 import (  # noqa: E402
    SuperagentOrchestrator,
    WorkModule,
    exact_mutation,
    exact_verifier,
)
from enterprise.engineering_control_plane_r24 import root  # noqa: E402


def check(name, fn):
    try:
        detail = fn()
        return {"name": name, "passed": True, "detail": detail}
    except Exception as exc:
        return {
            "name": name,
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def contract_check():
    p = ROOT / "architecture/R25/SYSTEM_EVOLUTION_CONTRACT.json"
    data = json.loads(p.read_text())
    assert data["release"] == "R25"
    assert data["invariants"]["promotion_requires_readback"] is True
    assert data["invariants"]["artifacts_are_content_addressed"] is True
    assert len(data["foundries"]) >= 18
    return {"contract_root": root(data), "foundries": len(data["foundries"])}


def superagent_check():
    with tempfile.TemporaryDirectory() as td:
        runtime = SuperagentOrchestrator(Path(td) / "ledger.jsonl")
        memory = WorkModule(
            module_id="runtime://kex/virtual-memory",
            owner="A.KEDDEH / KEDDEH_SYSTEMS",
            runtime="runtime://kex/virtual-memory",
            dependencies=(),
            invariants=("identity_preserved",),
            proof_ref="receipt://memory/readback",
            rollback_ref="checkpoint://memory",
        )
        casepath = WorkModule(
            module_id="app://casepath",
            owner="A.KEDDEH / KEDDEH_SYSTEMS",
            runtime="app://casepath",
            dependencies=(memory.module_id,),
            invariants=("source_preserved", "receipt_emitted"),
            proof_ref="receipt://casepath/readback",
            rollback_ref="checkpoint://casepath",
            frontage="https://casepath.com.au",
        )
        runtime.register_modules([memory, casepath])
        execution = runtime.execute_work_module(
            module_id=casepath.module_id,
            actor_role="IMPLEMENTER",
            input_state={"release": "R24", "state": "OBSERVED"},
            desired_state={"release": "R25", "state": "VERIFIED"},
            mutation=exact_mutation,
            verifier=exact_verifier,
        )
        assert execution["status"] == "VERIFIED"
        return {
            "ledger_root": runtime.ledger.ledger_root,
            "runnable_modules": runtime.runnable_modules(),
            "work_receipt_root": execution["receipt_root"],
        }


def overclaim_check():
    with tempfile.TemporaryDirectory() as td:
        runtime = SuperagentOrchestrator(Path(td) / "ledger.jsonl")
        result = runtime.reconcile_declared_observed(
            {"service://casepath": "VERIFIED"},
            {"service://casepath": "UNVERIFIED"},
        )
        assert result["deltas"][0]["classification"] == "OVERCLAIM"
        return result


def market_fabric_check():
    data = json.loads((ROOT / "architecture/R25/MARKET_SERVICE_FABRIC.json").read_text())
    required = set(data["global_market_gate"]["requires"])
    for service in data["services"]:
        missing = sorted(key for key in required if not service.get(key))
        assert not missing, f"{service['service_id']} missing {missing}"
    return {"service_count": len(data["services"]), "fabric_root": root(data)}


def main() -> int:
    checks = [
        check("SYSTEM_EVOLUTION_CONTRACT", contract_check),
        check("SUPERAGENT_EXECUTION", superagent_check),
        check("OVERCLAIM_RECONCILIATION", overclaim_check),
        check("MARKET_SERVICE_FABRIC", market_fabric_check),
    ]
    passed = all(item["passed"] for item in checks)
    receipt = {
        "schema": "kex.braink.r25.portable-qualification-receipt/v1",
        "release": "R25",
        "status": "VERIFIED" if passed else "FAILED",
        "executor": {
            "python": sys.version,
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        },
        "checks": checks,
    }
    receipt["receipt_root"] = root(receipt)
    output = ROOT / "artifacts/R25/R25_PORTABLE_QUALIFICATION_RECEIPT.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
