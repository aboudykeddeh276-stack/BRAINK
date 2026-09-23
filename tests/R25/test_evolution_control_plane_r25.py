from pathlib import Path

from enterprise.evolution_control_plane_r25 import (
    SuperagentOrchestrator,
    WorkModule,
    exact_mutation,
    exact_verifier,
)


def test_superagent_executes_verified_work_module(tmp_path: Path):
    runtime = SuperagentOrchestrator(tmp_path / "r25-ledger.jsonl")
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
        dependencies=("runtime://kex/virtual-memory",),
        invariants=("source_preserved", "receipt_emitted"),
        proof_ref="receipt://casepath/readback",
        rollback_ref="checkpoint://casepath",
        frontage="https://casepath.com.au",
    )
    runtime.register_modules([memory, casepath])
    assert runtime.runnable_modules() == ["app://casepath", "runtime://kex/virtual-memory"]

    result = runtime.execute_work_module(
        module_id="app://casepath",
        actor_role="IMPLEMENTER",
        input_state={"release": "R24", "state": "OBSERVED"},
        desired_state={"release": "R25", "state": "VERIFIED"},
        mutation=exact_mutation,
        verifier=exact_verifier,
    )
    assert result["status"] == "VERIFIED"
    assert result["verification"]["passed"] is True
    assert runtime.ledger.ledger_root == result["receipt_root"]


def test_non_mutating_role_cannot_execute_write(tmp_path: Path):
    runtime = SuperagentOrchestrator(tmp_path / "r25-ledger.jsonl")
    module = WorkModule(
        module_id="service://x",
        owner="A.KEDDEH / KEDDEH_SYSTEMS",
        runtime="runtime://x",
        dependencies=(),
        invariants=("proof",),
        proof_ref="receipt://x",
        rollback_ref="checkpoint://x",
    )
    runtime.register_modules([module])
    try:
        runtime.execute_work_module(
            module_id=module.module_id,
            actor_role="ARCHITECT",
            input_state={"x": 1},
            desired_state={"x": 2},
            mutation=exact_mutation,
            verifier=exact_verifier,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("architect role must not mutate")


def test_reconciliation_detects_overclaim(tmp_path: Path):
    runtime = SuperagentOrchestrator(tmp_path / "r25-ledger.jsonl")
    result = runtime.reconcile_declared_observed(
        {"service://casepath": "VERIFIED"},
        {"service://casepath": "UNVERIFIED"},
    )
    assert result["delta_count"] == 1
    assert result["deltas"][0]["classification"] == "OVERCLAIM"
