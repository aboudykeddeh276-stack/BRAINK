import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','src'))
from distributed_runtime import *

class DistributedRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.k=ToTSafetyKernel(); self.d=DistributedCoordinateDirectory(('n1','n2','n3'),self.k)
 def test_tot_requires_evidence(self):
  self.assertRaises(SafetyViolation,self.k.authorize,'OBSERVE','x','')
 def test_tot_rejects_undeclared_action(self):
  self.assertRaises(SafetyViolation,self.k.authorize,'DELETE','x','proof')
 def test_receipt_chain_root_changes(self):
  a=self.k.root;self.k.authorize('OBSERVE','x','proof');self.assertNotEqual(a,self.k.root)
 def test_majority_commit(self):
  r=self.d.commit('2,2',b'A','n1');self.assertEqual(r.generation,1);self.assertEqual(self.d.canonical('2,2'),r)
 def test_one_replica_loss_still_commits(self):
  self.d.set_online('n3',False);r=self.d.commit('2,2',b'A','n1');self.assertEqual(r.generation,1)
 def test_majority_loss_blocks_commit(self):
  self.d.set_online('n2',False);self.d.set_online('n3',False);self.assertRaises(CoordinateConflict,self.d.commit,'2,2',b'A','n1')
 def test_stale_replica_repaired(self):
  self.d.set_online('n3',False);self.d.commit('2,2',b'A','n1');self.d.set_online('n3',True);x=Layer2Reconciler().reconcile(self.d,'2,2');self.assertTrue(x['consistent']);self.assertEqual(x['actions']['n3'],'REPAIRED')
 def test_generation_advances(self):
  a=self.d.commit('2,2',b'A','n1');b=self.d.commit('2,2',b'B','n2');self.assertEqual((a.generation,b.generation),(1,2));self.assertEqual(b.previous_hash,a.value_hash)
 def test_zero_address_rejected(self): self.assertRaises(CoordinateConflict,self.d.commit,'0',b'A','n1')
 def test_unknown_proposer_rejected(self): self.assertRaises(CoordinateConflict,self.d.commit,'2,2',b'A','ghost')
 def test_split_without_quorum_has_no_canonical_state(self):
  self.d.commit('2,2',b'A','n1');self.d.set_online('n2',False);self.d.set_online('n3',False);self.assertRaises(CoordinateConflict,self.d.canonical,'2,2')
 def test_crash_fault_tolerance_does_not_prove_byzantine_safety(self):
  self.d.commit('2,2',b'A','n1');evil=CoordinateRecord('2,2',99,'evil','n3','wrong');self.d.replicas['n3'].state['2,2']=evil
  self.assertEqual(self.d.canonical('2,2').generation,1)
  # This only shows a single corrupt replica cannot form a majority; no signatures or Byzantine protocol exist.
  self.assertFalse(hasattr(self.d,'verify_signature'))

if __name__=='__main__': unittest.main(verbosity=2)
