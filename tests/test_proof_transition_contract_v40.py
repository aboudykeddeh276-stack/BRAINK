import unittest
from runtime.proof_transition import *
def retry(**kw):
 b=dict(operation_fingerprint='gha:head',failure_fingerprint='external:block',prerequisites={'billing':'BLOCKED','ui':'A'},relevant_prerequisites=frozenset({'billing'}),causal_prerequisites=frozenset({'billing'}),retry_count=0,retry_budget=2,failure_epoch='e1'); b.update(kw); return RetryContext(**b)
def tr(**kw):
 b=dict(operation_id='op1',operation_fingerprint='btc:getblocktemplate',subject='miner',subject_revision='s1',evidence_revision='s1',environment_id='env',environment_revision='envsha',evidence_class=EvidenceClass.TESTED,prior_state='CANDIDATE',resulting_state='TESTED',provenance=EvidenceProvenance('pytest','unit','e://1','mechanics','abc','sha256'),attempt_id='a1',evidence_attempt_id='a1',attempt_sequence=1,evidence_sequence=2,stage='MINER',prior_stage='TEMPLATE',evidence_scope='mechanics'); b.update(kw); return Transition(**b)
class ProofTransitionV40(unittest.TestCase):
 def test_21(self): self.assertEqual(decide_retry(retry(),retry()),TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION)
 def test_22(self): self.assertEqual(decide_retry(retry(),retry(prerequisites={'billing':'BLOCKED','ui':'B'})),TransitionDecision.NO_RETRY_IRRELEVANT_DELTA)
 def test_23(self): self.assertEqual(decide_retry(retry(causal_prerequisites=frozenset()),retry(prerequisites={'billing':'CLEAR','ui':'A'},causal_prerequisites=frozenset())),TransitionDecision.NO_RETRY_CAUSAL_LINK)
 def test_24(self): self.assertEqual(decide_retry(retry(),retry(failure_epoch='e2',prerequisites={'billing':'CLEAR','ui':'A'})),TransitionDecision.NO_RETRY_FAILURE_MISMATCH)
 def test_25(self): self.assertEqual(decide_retry(retry(retry_count=2),retry(prerequisites={'billing':'CLEAR','ui':'A'})),TransitionDecision.NO_RETRY_BUDGET_EXHAUSTED)
 def test_26(self): self.assertFalse(qualify_transition(tr(environment_revision='')).accepted)
 def test_27(self): self.assertFalse(qualify_transition(tr(provenance=EvidenceProvenance('','unit','r','mechanics'))).accepted)
 def test_28(self): self.assertIn('unit',audit_key_v40(tr()))
 def test_29(self): self.assertEqual(qualify_transition(tr(provenance=EvidenceProvenance('p','m','r','mechanics','abc',None))).reason,'INCOMPLETE_EVIDENCE_DIGEST')
 def test_30(self): self.assertEqual(qualify_transition(tr(evidence_scope='system')).reason,'EVIDENCE_SCOPE_MISMATCH')
 def test_31(self): self.assertEqual(qualify_transition(tr(evidence_class=EvidenceClass.OBSERVED,resulting_state='TESTED')).reason,'INSUFFICIENT_EVIDENCE_STRENGTH')
 def test_32(self): self.assertEqual(qualify_transition(tr(outcome=Outcome.BLOCKED,resulting_state='BLOCKED')).preserved_prior_state,'CANDIDATE')
 def test_33(self): self.assertEqual(qualify_transition(tr(outcome=Outcome.SUPERSEDED,resulting_state='SUPERSEDED')).reason,'SUPERSESSION_TARGET_REQUIRED')
 def test_34(self): self.assertEqual(qualify_transition(tr(attempt_sequence=0)).reason,'INVALID_TEMPORAL_SEQUENCE')
 def test_35(self): self.assertEqual(idempotency_key(tr()),idempotency_key(tr()))
 def test_36(self): self.assertEqual(tr().stage,'MINER')
 def test_37(self): self.assertEqual(qualify_transition(tr(stage='SUBMISSION',prior_stage='BITCOIN_CORE')).reason,'STAGE_SKIP')
 def test_38(self): self.assertEqual(qualify_transition(tr()).reason,'TRANSITION_EVIDENCE_BOUND')
 def test_39(self): self.assertIn('envsha',audit_key_v40(tr()))
 def test_40(self): self.assertTrue(qualify_transition(tr()).accepted)
if __name__=='__main__': unittest.main()
