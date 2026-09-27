from enterprise.recursive_operating_fabric import (
    RecursiveOperatingFabric,
    FabricNode,
    OperationalLine,
    AuthorityContext,
    LifecycleState,
    NodeKind,
    AdmissionError,
    PromotionError,
)


def base_fabric():
    f = RecursiveOperatingFabric()
    root_auth = AuthorityContext("authority://root", ("deploy", "execute", "verify", "observe"))
    root = FabricNode("build://root", NodeKind.BUILD, None, root_auth, metadata={"directive_semantic_root": "D1", "revision": 1})
    f.register(root)

    nodes = [
        FabricNode("skill://s1", NodeKind.SKILL, "build://root", root_auth.derive("authority://skill", ("deploy", "execute", "verify", "observe")), metadata={"directive_semantic_root": "D1"}),
        FabricNode("actuator://a1", NodeKind.ACTUATOR, "build://root", root_auth.derive("authority://actuator", ("deploy", "execute")), metadata={"directive_semantic_root": "D1"}),
        FabricNode("substrate://fs", NodeKind.SUBSTRATE, "build://root", root_auth.derive("authority://substrate", ("deploy",)), metadata={"directive_semantic_root": "D1"}),
        FabricNode("runtime://r1", NodeKind.RUNTIME, "build://root", root_auth.derive("authority://runtime", ("execute",)), metadata={"directive_semantic_root": "D1"}),
        FabricNode("observer://o1", NodeKind.OBSERVER, "build://root", root_auth.derive("authority://observer", ("observe",)), metadata={"directive_semantic_root": "D1"}),
        FabricNode("verifier://v1", NodeKind.VERIFIER, "build://root", root_auth.derive("authority://verifier", ("verify",)), metadata={"directive_semantic_root": "D1"}),
        FabricNode("evidence://p1", NodeKind.EVIDENCE, "build://root", root_auth.derive("authority://evidence", ()), metadata={"directive_semantic_root": "D1"}),
    ]
    for n in nodes:
        f.register(n)

    line = OperationalLine(
        line_id="line://deploy",
        what="deploy skill runtime",
        how="invoke actuator against explicit substrate",
        how_is="bounded deployment transaction",
        how_operates="write target artifact then read back target state",
        acts_on="artifact://skill-runtime",
        change="artifact materialised and runtime configuration updated",
        change_location="substrate://fs",
        observer_id="observer://o1",
        verifier_id="verifier://v1",
        evidence_predicate="target hash and post-state readback match",
        next_state_predicate="deployment evidence packet satisfies DEPLOYED",
        actuator_id="actuator://a1",
        substrate_id="substrate://fs",
        runtime_id="runtime://r1",
        persistence_id="evidence://p1",
        failure_behavior="retain prior state and return failure receipt",
        recovery_procedure="reconcile target and retry bounded transaction",
    )
    f.add_line("skill://s1", line)
    # Actuator itself must be operationally defined for recursive admission.
    f.add_line("actuator://a1", line)
    return f


def test_authority_cannot_expand_in_derived_context():
    root = AuthorityContext("root", ("read", "write"))
    try:
        root.derive("child", ("read", "admin"))
        assert False
    except AdmissionError as exc:
        assert "AUTHORITY_ESCALATION" in str(exc)


def test_recursive_admission_requires_operational_lines_and_defined_refs():
    f = base_fabric()
    report = f.descendant_admission("build://root")
    assert report["admitted"] is True
    assert report["node_count"] == 8


def test_unresolved_operation_semantics_are_rejected():
    f = RecursiveOperatingFabric()
    auth = AuthorityContext("root", ("deploy",))
    f.register(FabricNode("build://root", NodeKind.BUILD, None, auth))
    f.register(FabricNode("skill://bad", NodeKind.SKILL, "build://root", auth))
    bad = OperationalLine(
        "line://bad", "deploy", "TODO", "x", "x", "x", "x", "x", "x", "y", "z", "q",
        "missing", "missing", "missing", "missing", "fail", "recover"
    )
    try:
        f.add_line("skill://bad", bad)
        assert False
    except AdmissionError as exc:
        assert "UNRESOLVED_OR_FAKE_SEMANTICS" in str(exc) or "UNDEFINED_" in str(exc)


def test_state_cannot_skip_or_infer():
    f = base_fabric()
    try:
        f.promote("skill://s1", LifecycleState.EXECUTED)
        assert False
    except PromotionError as exc:
        assert "SEQUENTIAL_PROMOTION_REQUIRED" in str(exc)


def test_full_lifecycle_requires_target_specific_evidence():
    f = base_fabric()
    node = "skill://s1"

    f.record_evidence(node, "IMPLEMENTED", {
        "source_ref": "git://repo/path",
        "source_hash": "a" * 64,
        "implementation_readback": "blob:a",
    })
    f.promote(node, "IMPLEMENTED")

    f.record_evidence(node, "EXECUTED", {
        "command_id": "cmd-1",
        "execution_authority": "authority://skill",
        "gate_telemetry": "gate://1",
        "computational_transition": "input->output",
        "post_state_hash": "b" * 64,
        "exit_code": 0,
        "effect_observed": True,
    })
    f.promote(node, "EXECUTED")

    f.record_evidence(node, "DEPLOYED", {
        "target_substrate_id": "substrate://fs",
        "deployment_command_id": "cmd-deploy-1",
        "realization_readback": {"path": "/srv/skill", "hash": "c" * 64},
        "target_artifact_hash": "c" * 64,
    })
    f.promote(node, "DEPLOYED")

    f.record_evidence(node, "ACTIVE", {
        "participation_probe": "probe://runtime",
        "heartbeat_observed_at": "2026-09-28T08:00:00+09:30",
        "runtime_identity": "runtime://r1",
        "participating": True,
    })
    f.promote(node, "ACTIVE")

    f.record_evidence(node, "FUNCTIONING", {
        "specified_behavior": "returns deterministic output",
        "expected_result": {"ok": True},
        "observed_result": {"ok": True},
        "behavior_passed": True,
    })
    f.promote(node, "FUNCTIONING")

    f.record_evidence(node, "INTEGRATED", {
        "integration_edges": ["edge://api", "edge://vfs"],
        "edge_readbacks": [True, True],
    })
    f.promote(node, "INTEGRATED")

    f.record_evidence(node, "VERIFIED", {
        "actor_id": "actor://builder",
        "verifier_id": "verifier://v1",
        "verifier_report_ref": "report://77",
        "post_state_hash": "d" * 64,
        "independent_readback": {"ok": True},
        "receipt_hash": "e" * 64,
    })
    f.promote(node, "VERIFIED")

    f.record_evidence(node, "SUSTAINED", {
        "observation_count": 3,
        "observation_window": "15m",
        "recovery_procedure": "restart and reconcile",
        "recovery_readback": {"rejoined": True},
    })
    f.promote(node, "SUSTAINED")

    assert f.nodes[node].state == LifecycleState.SUSTAINED
    assert len(f.nodes[node].state_history) == 8


def test_deployed_requires_substrate_realization_readback():
    f = base_fabric()
    n = "skill://s1"
    f.record_evidence(n, "IMPLEMENTED", {"source_ref": "x", "source_hash": "a", "implementation_readback": "x"})
    f.promote(n, "IMPLEMENTED")
    f.record_evidence(n, "EXECUTED", {
        "command_id": "c", "execution_authority": "a", "gate_telemetry": "g",
        "computational_transition": "x", "post_state_hash": "h", "exit_code": 0, "effect_observed": True
    })
    f.promote(n, "EXECUTED")
    f.record_evidence(n, "DEPLOYED", {
        "target_substrate_id": "s", "deployment_command_id": "d",
        "realization_readback": False, "target_artifact_hash": "h"
    })
    try:
        f.promote(n, "DEPLOYED")
        assert False
    except PromotionError as exc:
        assert "MISSING" in str(exc) or "WITHOUT_SUBSTRATE_READBACK" in str(exc)


def test_actor_cannot_verify_self():
    f = base_fabric()
    n = "skill://s1"
    chain = [
        ("IMPLEMENTED", {"source_ref": "x", "source_hash": "a", "implementation_readback": "x"}),
        ("EXECUTED", {"command_id": "c", "execution_authority": "a", "gate_telemetry": "g", "computational_transition": "x", "post_state_hash": "h", "exit_code": 0, "effect_observed": True}),
        ("DEPLOYED", {"target_substrate_id": "s", "deployment_command_id": "d", "realization_readback": {"ok": True}, "target_artifact_hash": "h"}),
        ("ACTIVE", {"participation_probe": "p", "heartbeat_observed_at": "t", "runtime_identity": "r", "participating": True}),
        ("FUNCTIONING", {"specified_behavior": "b", "expected_result": 1, "observed_result": 1, "behavior_passed": True}),
        ("INTEGRATED", {"integration_edges": ["e"], "edge_readbacks": [True]}),
    ]
    for state, packet in chain:
        f.record_evidence(n, state, packet)
        f.promote(n, state)
    f.record_evidence(n, "VERIFIED", {
        "actor_id": "same", "verifier_id": "same", "verifier_report_ref": "r",
        "post_state_hash": "p", "independent_readback": {"ok": True}
    })
    try:
        f.promote(n, "VERIFIED")
        assert False
    except PromotionError as exc:
        assert "ACTOR_CANNOT_VERIFY_OWN_DELIVERY" in str(exc)


def test_optimisation_requires_demonstrated_mechanics_and_preserves_invariants():
    f = base_fabric()
    try:
        f.optimise("skill://s1", {}, {"authority": True})
        assert False
    except PromotionError as exc:
        assert "DEMONSTRATED_MECHANICS" in str(exc)

    f.nodes["skill://s1"].state = LifecycleState.FUNCTIONING
    metrics = {
        "execution_latency": 1,
        "failure_recovery": 1,
        "idempotency": 1,
        "concurrency": 1,
        "persistence": 1,
        "evidence_completeness": 1,
        "dependency_depth": 1,
        "duplicate_work": 0,
        "actuator_reliability": 1,
        "verification_cost": 1,
    }
    receipt = f.optimise("skill://s1", metrics, {"authority": True, "verification": True})
    assert receipt["requires_redeployment"] is True

    try:
        f.optimise("skill://s1", metrics, {"authority": True, "verification": False})
        assert False
    except PromotionError as exc:
        assert "INVARIANT_FAILURE" in str(exc)


def test_one_failed_actuator_does_not_fail_parent_if_alternative_succeeds():
    result = RecursiveOperatingFabric.parent_outcome([
        {"actuator": "a", "eligible": True, "status": "FAILED"},
        {"actuator": "b", "eligible": True, "status": "FUNCTIONING"},
    ])
    assert result == "DEGRADED_CONTINUE_ELIGIBLE_PATHS"
