import unittest
from runtime.proof_transition import *


def retry(**kw):
    base=dict(operation_fingerprint='gha:head',failure_fingerprint='external:block',prerequisites={'billing':'BLOCKED','ui':'A'},relevant_prerequisites=frozenset({'billing'}),retry_count=0,retry_budget=2)
    base.update(kw); return RetryContext(**base)


def transition(**kw):
    base=dict(operation_id='op1',operation_fingerprint='btc:getblocktemplate',subject='runtime/btc_miner_runtime.py',subject_revision='sha1',evidence_revision='sha1',environment_id='env1',evidence_class=EvidenceClass.TESTED,prior_state='CANDIDATE',resulting_state='TESTED',provenance=EvidenceProvenance('pytest','unit','evidence://1','mechanics'),attempt_id='a1',evidence_attempt_id='a1',attempt_sequence=1,evidence_sequence=2)
    base.update(kw); return Transition(**base)


class ProofTransitionV20(unittest.TestCase):
    def test_01_unchanged_precondition_no_retry(self):
        self.assertEqual(decide_retry(retry(),retry()),TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION)
    def test_02_relevant_delta_allows_retry(self):
        self.assertEqual(decide_retry(retry(),retry(prerequisites={'billing':'CLEAR','ui':'A'})),TransitionDecision.RETRY_ALLOWED)
    def test_03_irrelevant_delta_does_not_allow_retry(self):
        self.assertEqual(decide_retry(retry(),retry(prerequisites={'billing':'BLOCKED','ui':'B'})),TransitionDecision.NO_RETRY_IRRELEVANT_DELTA)
    def test_04_operation_mismatch_rejected(self):
        self.assertEqual(decide_retry(retry(),retry(operation_fingerprint='other')),TransitionDecision.NO_RETRY_OPERATION_MISMATCH)
    def test_05_failure_mismatch_rejected(self):
        self.assertEqual(decide_retry(retry(),retry(failure_fingerprint='different')),TransitionDecision.NO_RETRY_FAILURE_MISMATCH)
    def test_06_retry_budget_is_bounded(self):
        self.assertEqual(decide_retry(retry(retry_count=2),retry(prerequisites={'billing':'CLEAR','ui':'A'})),TransitionDecision.NO_RETRY_BUDGET_EXHAUSTED)
    def test_07_revision_mismatch_rejected(self):
        self.assertEqual(qualify_transition(transition(evidence_revision='sha2')).reason,'SUBJECT_EVIDENCE_REVISION_MISMATCH')
    def test_08_attempt_replay_rejected(self):
        self.assertEqual(qualify_transition(transition(evidence_attempt_id='old')).reason,'EVIDENCE_ATTEMPT_REPLAY_OR_MISBIND')
    def test_09_temporal_inversion_rejected(self):
        self.assertEqual(qualify_transition(transition(attempt_sequence=3,evidence_sequence=2)).reason,'EVIDENCE_PRECEDES_ATTEMPT')
    def test_10_missing_environment_rejected(self):
        self.assertEqual(qualify_transition(transition(environment_id='')).reason,'INCOMPLETE_PROVENANCE_ENVELOPE')
    def test_11_missing_producer_rejected(self):
        p=EvidenceProvenance('','unit','e://1','scope'); self.assertFalse(qualify_transition(transition(provenance=p)).accepted)
    def test_12_illegal_state_transition_rejected(self):
        self.assertEqual(qualify_transition(transition(resulting_state='SUBMISSION_ACCEPTED')).reason,'ILLEGAL_STATE_TRANSITION')
    def test_13_carrier_block_cannot_fail_source(self):
        q=qualify_transition(transition(evidence_class=EvidenceClass.BLOCKED,resulting_state='FAILED',failure_scope='CARRIER_BEFORE_EXECUTION')); self.assertFalse(q.accepted)
    def test_14_downstream_block_preserves_prior(self):
        q=qualify_transition(transition(evidence_class=EvidenceClass.BLOCKED,resulting_state='BLOCKED')); self.assertTrue(q.accepted); self.assertEqual(q.preserved_prior_state,'CANDIDATE')
    def test_15_normal_bound_transition_accepted(self):
        self.assertTrue(qualify_transition(transition()).accepted)
    def test_16_audit_key_binds_revision_environment_operation_attempt(self):
        self.assertEqual(audit_key(transition()),('runtime/btc_miner_runtime.py','sha1','env1','op1','a1'))
    def test_17_qualified_cannot_jump_to_submission(self):
        q=qualify_transition(transition(prior_state='QUALIFIED',resulting_state='SUBMISSION_ACCEPTED')); self.assertFalse(q.accepted)
    def test_18_core_template_boundary_is_explicit(self):
        q=qualify_transition(transition(prior_state='BITCOIN_CORE_QUALIFIED',resulting_state='TEMPLATE_ACQUIRED')); self.assertTrue(q.accepted)
    def test_19_template_to_mining_boundary_is_explicit(self):
        q=qualify_transition(transition(prior_state='TEMPLATE_ACQUIRED',resulting_state='MINING_ACTIVE')); self.assertTrue(q.accepted)
    def test_20_candidate_submission_boundary_is_explicit(self):
        q=qualify_transition(transition(prior_state='CANDIDATE_FOUND',resulting_state='SUBMISSION_ACCEPTED')); self.assertTrue(q.accepted)

if __name__=='__main__': unittest.main()
