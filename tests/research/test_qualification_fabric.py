from __future__ import annotations

from research.qualification_fabric.qualification_fabric import Executor, Receipt, reconcile, select_executor


def _claim():
    return {
        "claim_id": "C1",
        "proof_requirements": [
            {"proof_id": "P1", "minimum_level": 5, "description": "integration"},
            {"proof_id": "P2", "minimum_level": 6, "description": "adversarial"},
        ],
        "required_evidence_level": 6,
        "invalid_overclaims": ["do not claim cross-machine proof"],
    }


def test_executor_selection_is_capability_based_not_ci_brand_based():
    executors = [
        Executor("github-hosted", "ci", ("python",), False),
        Executor("resident-host", "resident", ("python", "tcp-loopback", "persistent-state"), True),
        Executor("container", "container", ("python", "tcp-loopback"), True),
    ]
    selected = select_executor(["python", "tcp-loopback"], executors)
    assert selected is not None
    assert selected.executor_id == "container"


def test_unavailable_executor_blocks_but_does_not_reject_claim():
    result = reconcile(
        _claim(),
        [
            Receipt("C1", "P1", "resident-host", "PASS", 5, "integration observed"),
            Receipt("C1", "P2", "github-hosted", "EXECUTOR_UNAVAILABLE", 0, "runner never instantiated"),
        ],
    )
    assert result["conclusion"] == "BLOCKED"
    assert result["promotion_allowed"] is False


def test_failed_proof_rejects_claim():
    result = reconcile(
        _claim(),
        [
            Receipt("C1", "P1", "resident-host", "PASS", 5, "integration observed"),
            Receipt("C1", "P2", "resident-host", "FAIL", 6, "mismatch accepted"),
        ],
    )
    assert result["conclusion"] == "REJECTED"
    assert result["promotion_allowed"] is False


def test_all_required_proofs_at_required_level_support_claim():
    result = reconcile(
        _claim(),
        [
            Receipt("C1", "P1", "resident-host", "PASS", 5, "integration observed"),
            Receipt("C1", "P2", "resident-host", "PASS", 6, "mismatch rejected"),
        ],
    )
    assert result["conclusion"] == "SUPPORTED"
    assert result["highest_observed_evidence_level"] == 6
    assert result["promotion_allowed"] is True
