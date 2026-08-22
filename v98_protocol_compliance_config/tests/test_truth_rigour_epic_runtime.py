import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from keddeh_truth_rigour_epic_runtime import *

class TruthRigourEpicTests(unittest.TestCase):
    def test_truth_claim_is_property_scoped(self):
        c=Claim("x","p","d",("truth","scope","evidence")).evaluate({"truth","scope","evidence"},set(),True)
        self.assertEqual(c.state,ClaimState.ESTABLISHED_PROPERTY)

    def test_counterexample_prevents_promotion(self):
        c=Claim("x","p","d",("a","b")).evaluate({"a"},{"b"},False)
        self.assertEqual(c.state,ClaimState.CONTRADICTED)

    def test_zero_state_typing(self):
        p=exhaustive_zero_state_proof()
        self.assertEqual(p["state_count"],5)
        self.assertEqual(p["ordered_pairs"],25)
        self.assertFalse(p["zero_is_weighted_state"])
        self.assertTrue(p["reference_zero_separate_type"])
        self.assertTrue(p["present_zero_rejected"])

    def test_observer_translation(self):
        A=ObserverFrame("A",(0,0,0),1)
        B=ObserverFrame("B",(10,-5,2),2)
        physical=(12.0,1.0,4.0)
        xa=A.observe(physical); xb=B.observe(physical)
        self.assertEqual(translate_observation(xa,A,B),xb)
        self.assertAlmostEqual(observer_invariant_distance(xa,xb,A,B),0,places=12)

    def test_86_lane_258_work_multiplex(self):
        work=list(range(258)); lanes=Multiplex(86).partition(work)
        proof=Multiplex.verify_partition(work,lanes)
        self.assertTrue(proof["complete"])
        self.assertTrue(proof["no_duplicate_assignment"])
        self.assertTrue(all(len(v)==3 for v in lanes.values()))

    def test_bilateral_translation(self):
        lex=LexiconILLLM()
        receipt=lex.bilateral("roman","arabic",lambda x:{"I":1,"V":5}[x],lambda x:{1:"I",5:"V"}[x],["I","V"])
        self.assertTrue(receipt["all_preserved"])

    def test_three_body_force_balance(self):
        r=force_balance_residual([1,1,1],[(1,0,0),(-.5,.866025403784,0),(-.5,-.866025403784,0)])
        self.assertLess(r,1e-10)

    def test_activation_and_readback(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            receipt=activate(root)
            p=root/"evidence/truth_rigour_epic_activation_receipt.json"
            self.assertTrue(p.exists())
            saved=json.loads(p.read_text())
            self.assertEqual(saved["proof"],receipt["proof"])
            self.assertEqual(saved["chain_root"],receipt["chain_root"])

if __name__=="__main__":
    unittest.main(verbosity=2)
