from braink_runtime.process_engine import ExecutionContract, ProcessEngine, ProcessViolation, make_receipt


def test_core_promotes_only_after_valid_receipt():
    engine = ProcessEngine()
    engine.register_capability("PING", lambda c: make_receipt(c, status="PASS", observed={"pong": True}))
    contract = ExecutionContract("c1", "READY", "USER_OPERATOR", "NODE_01", "PING")
    result = engine.execute(contract)
    assert result["validation"] == "PASS"
    assert result["next_state"] == "READY:QUALIFIED"


def test_capability_cannot_change_target_via_receipt():
    engine = ProcessEngine()
    def bad(c):
        r = make_receipt(c, status="PASS", observed={})
        return type(r)(r.contract_id, "OTHER_NODE", r.capability, r.status, r.observed, r.started_ns, r.completed_ns, r.receipt_type)
    engine.register_capability("PING", bad)
    contract = ExecutionContract("c2", "READY", "USER_OPERATOR", "NODE_01", "PING")
    try:
        engine.execute(contract)
    except ProcessViolation as exc:
        assert "TARGET_MISMATCH" in str(exc)
    else:
        raise AssertionError("target authority drift was accepted")


def test_unbound_capability_fails_closed():
    engine = ProcessEngine()
    contract = ExecutionContract("c3", "READY", "USER_OPERATOR", "NODE_01", "MISSING")
    try:
        engine.execute(contract)
    except ProcessViolation as exc:
        assert "CAPABILITY_UNBOUND" in str(exc)
    else:
        raise AssertionError("unbound capability was executed")
