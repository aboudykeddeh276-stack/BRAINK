import unittest

try:
    from runtime.proof_transition import (
        EvidenceClass,
        Transition,
        TransitionDecision,
        decide_retry,
        qualify_transition,
    )
except ModuleNotFoundError as exc:
    raise AssertionError(
        "RED: runtime.proof_transition does not yet exist; proof-bearing transition contract is unimplemented"
    ) from exc


class ProofTransitionContractTests(unittest.TestCase):
    def test_identical_external_failure_without_prerequisite_delta_cannot_retry(self):
        decision = decide_retry(
            operation_fingerprint="github-actions:exact-head",
            previous_failure="EXTERNAL_EXECUTION_BLOCKED",
            previous_prerequisites={"billing_gate": "BLOCKED"},
            current_prerequisites={"billing_gate": "BLOCKED"},
        )
        self.assertEqual(decision, TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION)

    def test_changed_relevant_prerequisite_can_retry(self):
        decision = decide_retry(
            operation_fingerprint="github-actions:exact-head",
            previous_failure="EXTERNAL_EXECUTION_BLOCKED",
            previous_prerequisites={"billing_gate": "BLOCKED"},
            current_prerequisites={"billing_gate": "CLEAR"},
        )
        self.assertEqual(decision, TransitionDecision.RETRY_ALLOWED)

    def test_evidence_cannot_be_rebound_to_changed_subject_revision(self):
        transition = Transition(
            operation_id="op-1",
            subject="runtime/btc_miner_runtime.py",
            subject_revision="sha-old",
            evidence_revision="sha-new",
            evidence_class=EvidenceClass.TESTED,
            prior_state="CANDIDATE",
            resulting_state="QUALIFIED",
        )
        result = qualify_transition(transition)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "SUBJECT_EVIDENCE_REVISION_MISMATCH")

    def test_blocked_carrier_does_not_become_source_failure(self):
        transition = Transition(
            operation_id="op-2",
            subject="runtime/btc_miner_runtime.py",
            subject_revision="sha-1",
            evidence_revision="sha-1",
            evidence_class=EvidenceClass.BLOCKED,
            prior_state="CANDIDATE",
            resulting_state="FAILED",
            failure_scope="CARRIER_BEFORE_EXECUTION",
        )
        result = qualify_transition(transition)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "CARRIER_BLOCK_CANNOT_CLASSIFY_SOURCE_FAILED")

    def test_verified_progress_is_preserved_when_downstream_step_blocks(self):
        transition = Transition(
            operation_id="op-3",
            subject="bitcoin-core:getblocktemplate",
            subject_revision="core-tip-A",
            evidence_revision="core-tip-A",
            evidence_class=EvidenceClass.BLOCKED,
            prior_state="BITCOIN_CORE_QUALIFIED",
            resulting_state="BLOCKED",
        )
        result = qualify_transition(transition)
        self.assertTrue(result.accepted)
        self.assertEqual(result.preserved_prior_state, "BITCOIN_CORE_QUALIFIED")


if __name__ == "__main__":
    unittest.main()
