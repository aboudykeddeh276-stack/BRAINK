from runtime.R25.system_evolution_runtime import Capability, EvolutionRuntime, exact_repair


def test_reconciliation_is_deterministic_and_receipted():
    runtime = EvolutionRuntime()
    receipt = runtime.reconcile(
        actor="BRAINK_SUPERAGENT",
        current_state={"version": 1, "services": ["a"]},
        desired_state={"version": 2, "services": ["a", "b"]},
        repair=exact_repair,
        lineage=["runtime://braink/root", "runtime://braink/r25"],
    )
    assert receipt.operation == "RECONCILE"
    assert receipt.input_hash != receipt.output_hash
    assert receipt.proof["readback_equal"] is True
    assert receipt.rollback["checkpoint_id"] in runtime.checkpoints
    assert runtime.ledger.verify() is True


def test_capability_rejects_orphan_service():
    runtime = EvolutionRuntime()
    invalid = Capability(
        capability_id="service://orphan",
        owner="",
        runtime="runtime://missing",
        proof="proof://missing",
        rollback="rollback://missing",
    )
    try:
        runtime.discover([invalid])
    except ValueError as exc:
        assert "owner" in str(exc)
    else:
        raise AssertionError("orphan capability must be rejected")


def test_market_qualification_requires_service_contract_and_value():
    runtime = EvolutionRuntime()
    capability = Capability(
        capability_id="service://casepath/preparation",
        owner="A.KEDDEH / KEDDEH_SYSTEMS",
        runtime="app://casepath",
        proof="receipt://casepath/readback",
        rollback="checkpoint://casepath",
        projection="https://casepath.com.au",
    )
    runtime.discover([capability])
    blocked = runtime.qualify_market_service(
        capability.capability_id,
        {"customer_problem": "Prepare structured matter records"},
    )
    assert blocked["status"] == "BLOCKED"

    qualified = runtime.qualify_market_service(
        capability.capability_id,
        {
            "customer_problem": "Prepare structured matter records",
            "service_contract": "source -> derived model -> document -> receipt",
            "proof": "outside-in readback and deterministic receipt",
            "value_metric": "reduced preparation effort with auditable source preservation",
        },
    )
    assert qualified["status"] == "QUALIFIED"
