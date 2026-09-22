import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','src'))
from layer1_9_reconciler import *

class L19Tests(unittest.TestCase):
 def payloads(self,x='A'): return {i:{'value':x,'layer':i} for i in range(1,10)}
 def test_full_chain(self):
  r=Layer1to9Reconciler();s=r.reconcile_all(1,self.payloads());self.assertEqual(len(s),9);self.assertTrue(r.verify());self.assertEqual(r.root,s[-1].output_root)
 def test_deterministic_root(self):
  a=Layer1to9Reconciler();b=Layer1to9Reconciler();a.reconcile_all(1,self.payloads());b.reconcile_all(1,self.payloads());self.assertEqual(a.root,b.root)
 def test_payload_change_changes_root(self):
  a=Layer1to9Reconciler();b=Layer1to9Reconciler();a.reconcile_all(1,self.payloads('A'));b.reconcile_all(1,self.payloads('B'));self.assertNotEqual(a.root,b.root)
 def test_skip_layer_rejected(self):
  r=Layer1to9Reconciler();self.assertRaises(LayerViolation,r.apply,2,1,'GENESIS',{})
 def test_wrong_upstream_rejected(self):
  r=Layer1to9Reconciler();self.assertRaises(LayerViolation,r.apply,1,1,'evil',{})
 def test_stale_generation_rejected(self):
  r=Layer1to9Reconciler();r.apply(1,2,'GENESIS',{});self.assertRaises(LayerViolation,r.apply,1,1,'GENESIS',{})
 def test_upstream_change_invalidates_downstream(self):
  r=Layer1to9Reconciler();r.reconcile_all(1,self.payloads());r.apply(1,2,'GENESIS',{'value':'B'});self.assertEqual(set(r.state),{1});self.assertRaises(LayerViolation,lambda:r.root)
 def test_incomplete_payload_set_rejected(self):
  r=Layer1to9Reconciler();p=self.payloads();p.pop(5);self.assertRaises(LayerViolation,r.reconcile_all,1,p)
 def test_zero_generation_rejected(self):
  r=Layer1to9Reconciler();self.assertRaises(LayerViolation,r.apply,1,0,'GENESIS',{})

if __name__=='__main__':unittest.main(verbosity=2)
