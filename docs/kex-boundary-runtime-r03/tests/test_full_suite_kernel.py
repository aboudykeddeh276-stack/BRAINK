import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','src'))
from full_suite_kernel import *
from distributed_runtime import CoordinateConflict

class FullSuiteTests(unittest.TestCase):
 def test_end_to_end(self):
  k=BRAINKSoftwareKernel();r=k.execute('2,2',b'BRAINK');self.assertTrue(r.consistent);self.assertEqual(r.generation,1);self.assertEqual(len(r.layer9_root),64);self.assertEqual(len(r.evidence_root),64)
 def test_quorum_loss_fails_closed(self):
  k=BRAINKSoftwareKernel();k.directory.set_online('n2',False);k.directory.set_online('n3',False);self.assertRaises(CoordinateConflict,k.execute,'2,2',b'BRAINK')
 def test_same_input_reproducible_layer_root(self):
  a=BRAINKSoftwareKernel();b=BRAINKSoftwareKernel();self.assertEqual(a.execute('2,2',b'X').layer9_root,b.execute('2,2',b'X').layer9_root)
 def test_payload_change_changes_directory_and_layer_roots(self):
  a=BRAINKSoftwareKernel();b=BRAINKSoftwareKernel();x=a.execute('2,2',b'X');y=b.execute('2,2',b'Y');self.assertNotEqual(x.directory_hash,y.directory_hash);self.assertNotEqual(x.layer9_root,y.layer9_root)

if __name__=='__main__':unittest.main(verbosity=2)
