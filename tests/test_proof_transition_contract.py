import unittest
from runtime.proof_transition import *
def retry(**kw):
    base=dict(operation_fingerprint='gha:head',failure_fingerprint='external:block',prerequisites={'billing':'BLOCKED','ui':'A'},relevant_prerequisites=frozenset({'billing'}),retry_count=0,retry_budget=2); base.update(kw); return RetryContext(**base)
def transition(**kw):
    base=dict(operation_id='op1',operation_fingerprint='btc:getblocktemplate',subject='runtime/btc_miner_runtime.py',subject_revision='sha1',evidence_revision='sha1',environment_id='env1',environment_revision='envrev1',evidence_class=EvidenceClass.TESTED,prior_state='CANDIDATE',resulting_state='TESTED',provenance=EvidenceProvenance('pytest','unit','evidence://1','mechanics'),attempt_id='a1',evidence_attempt_id='a1',attempt_sequence=1,evidence_sequence=2); base.update(kw); return Transition(**base)
class ProofTransitionV20Regression(unittest.TestCase):
    def test_01(self): self.assertEqual(decide_retry(retry(),retry()),TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION)
    def test_02(self): self.assertEqual(decide_retry(retry(),retry(prerequisites={'billing':'CLEAR','ui':'A'})),TransitionDecision.RETRY_ALLOWED)
    def test_03(self): self.assertEqual(decide_retry(retry(),retry(prerequisites={'billing':'BLOCKED','ui':'B'})),TransitionDecision.NO_RETRY_IRRELEVANT_DELTA)
    def test_04(self): self.assertEqual(decide_retry(retry(),retry(operation_fingerprint='other')),TransitionDecision.NO_RETRY_OPERATION_MISMATCH)
    def test_05(self): self.assertEqual(decide_retry(retry(),retry(failure_fingerprint='different')),TransitionDecision.NO_RETRY_FAILURE_MISMATCH)
    def test_06(self): self.assertEqual(decide_retry(retry(retry_count=2),retry(prerequisites={'billing':'CLEAR','ui':'A'})),TransitionDecision.NO_RETRY_BUDGET_EXHAUSTED)
    def test_07(self): self.assertEqual(qualify_transition(transition(evidence_revision='sha2')).reason,'SUBJECT_EVIDENCE_REVISION_MISMATCH')
    def test_08(self): self.assertEqual(qualify_transition(transition(evidence_attempt_id='old')).reason,'EVIDENCE_ATTEMPT_REPLAY_OR_MISBIND')
    def test_09(self): self.assertEqual(qualify_transition(transition(attempt_sequence=3,evidence_sequence=2)).reason,'EVIDENCE_PRECEDES_ATTEMPT')
    def test_10(self): self.assertEqual(qualify_transition(transition(environment_id='')).reason,'INCOMPLETE_PROVENANCE_ENVELOPE')
    def test_11(self): self.assertFalse(qualify_transition(transition(provenance=EvidenceProvenance('','unit','e://1','scope'))).accepted)
    def test_12(self): self.assertEqual(qualify_transition(transition(resulting_state='SUBMISSION_ACCEPTED')).reason,'ILLEGAL_STATE_TRANSITION')
    def test_13(self): self.assertFalse(qualify_transition(transition(evidence_class=EvidenceClass.BLOCKED,resulting_state='FAILED',failure_scope='CARRIER_BEFORE_EXECUTION')).accepted)
    def test_14(self): self.assertTrue(qualify_transition(transition(evidence_class=EvidenceClass.BLOCKED,resulting_state='BLOCKED')).accepted)
    def test_15(self): self.assertTrue(qualify_transition(transition()).accepted)
    def test_16(self): self.assertEqual(audit_key(transition()),('runtime/btc_miner_runtime.py','sha1','env1','op1','a1'))
    def test_17(self): self.assertFalse(qualify_transition(transition(prior_state='QUALIFIED',resulting_state='SUBMISSION_ACCEPTED')).accepted)
    def test_18(self): self.assertTrue(qualify_transition(transition(prior_state='BITCOIN_CORE_QUALIFIED',resulting_state='TEMPLATE_ACQUIRED',stage='TEMPLATE',prior_stage='BITCOIN_CORE')).accepted)
    def test_19(self): self.assertTrue(qualify_transition(transition(prior_state='TEMPLATE_ACQUIRED',resulting_state='MINING_ACTIVE',stage='MINER',prior_stage='TEMPLATE')).accepted)
    def test_20(self): self.assertTrue(qualify_transition(transition(prior_state='CANDIDATE_FOUND',resulting_state='SUBMISSION_ACCEPTED',stage='SUBMISSION',prior_stage='MINER')).accepted)
if __name__=='__main__': unittest.main()
