from braink_runtime.epic import Claim, EpicGate, EvidenceRef, assert_epic_non_mutating


def test_child_execution_is_not_parent_execution():
    gate = EpicGate([
        EvidenceRef(
            evidence_id="E1",
            subject="COUNT_JOB_1",
            predicate="RESULT",
            value=42,
            source="NODE_RECEIPT",
            receipt="sha256:child",
            executor="CHILD_A",
            router="PARENT_A",
            lineage_parent="PARENT_A",
        )
    ])
    child_claim = Claim(
        claim_id="C1",
        subject="COUNT_JOB_1",
        predicate="RESULT",
        expected=42,
        requires_receipt=True,
        asserted_executor="CHILD_A",
    )
    parent_claim = Claim(
        claim_id="C2",
        subject="COUNT_JOB_1",
        predicate="RESULT",
        expected=42,
        requires_receipt=True,
        asserted_executor="PARENT_A",
    )
    assert gate.decide(child_claim).status == "QUALIFIED"
    assert gate.decide(parent_claim).status == "REJECTED"


def test_lineage_does_not_imply_authority_or_execution():
    gate = EpicGate([
        EvidenceRef(
            evidence_id="E2",
            subject="JOB_2",
            predicate="STATUS",
            value="PASS",
            source="READBACK",
            executor="GRANDCHILD_X",
            lineage_parent="CHILD_X",
            router="PARENT_X",
            validator="PEER_Y",
        )
    ])
    decision = gate.decide(Claim(
        claim_id="C3",
        subject="JOB_2",
        predicate="STATUS",
        expected="PASS",
        asserted_executor="PARENT_X",
    ))
    assert decision.status == "REJECTED"


def test_unobserved_or_unreceipted_claims_do_not_promote():
    gate = EpicGate([
        EvidenceRef(
            evidence_id="E3",
            subject="JOB_3",
            predicate="STATUS",
            value="PASS",
            source="CONFIG",
            observed=False,
        ),
        EvidenceRef(
            evidence_id="E4",
            subject="JOB_4",
            predicate="STATUS",
            value="PASS",
            source="READBACK",
            observed=True,
        ),
    ])
    assert gate.decide(Claim("C4", "JOB_3", "STATUS", "PASS")).status == "UNOBSERVED"
    assert gate.decide(Claim("C5", "JOB_4", "STATUS", "PASS", requires_receipt=True)).status == "PARTIAL"


def test_epic_has_no_runtime_mutation_authority():
    boundary = assert_epic_non_mutating()
    assert boundary["runtime_mutation"] is False
    assert boundary["authority_assignment"] is False
    assert boundary["executor_selection"] is False
    assert boundary["state_promotion"] is False
    assert boundary["claim_gating"] is True
