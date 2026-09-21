import os,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','src'))
from kex_boundary import *
class RuntimeTests(unittest.TestCase):
 def setUp(self):self.node=NodeDef('casepath.hci.card','il-llm://node/hci-card',1,'dumb',('label',),('event',),(('surface','html'),))
 def test_roundtrip(self):
  for s in (b'',bytes([0]),bytes([1]),bytes([0,0,1,1,1,0,0,0,0,1,1,1]),bytes([0,1])*100):self.assertEqual(decode_ab(encode_ab(s)),s)
 def test_noncanonical_rejected(self):
  b=bytearray(encode_ab(bytes([0,0,1,1])));b[7]=65;b[8]=65;self.assertRaises(CodecError,decode_ab,bytes(b))
 def test_truncation_rejected(self):self.assertRaises(CodecError,decode_ab,encode_ab(bytes([1,0,1,0,1]))[:-1])
 def test_definition_stable_instances_distinct(self):
  h=self.node.definition_hash;a=instantiate(self.node,'html','i1');b=instantiate(self.node,'html','i2');a.state['x']=1;a.observer={'o':'a'};a.attribution.append({'e':1});self.assertNotEqual(a.instance_id,b.instance_id);self.assertEqual(h,self.node.definition_hash);self.assertNotIn('x',b.state)
 def test_directory_conflict(self):
  d=CoordinateDirectory();d.register('2,2',self.node.definition_hash);self.assertRaises(ValueError,d.register,'2,2','other')
 def test_reconcile(self):
  r=Layer2Reconciler().reconcile({'definition_hash':self.node.definition_hash},[{'definition_hash':self.node.definition_hash,'instance_id':'i1'},{'definition_hash':'bad','instance_id':'i2'}]);self.assertFalse(r['consistent']);self.assertEqual(len(r['rejected']),1)
 def test_tot_gate(self):
  k=ToTSafetyKernel();self.assertTrue(k.transition(self.node,'project',{'target':'html'})['accepted']);self.assertRaises(ValueError,k.transition,self.node,'delete',{})
 def test_html_projection(self):
  h=project_html(self.node,instantiate(self.node,'html','i1'));self.assertIn('data-kex-node',h);self.assertIn('i1',h)
 def test_fault_injection_bit_flip(self):
  b=bytearray(encode_ab(bytes([0,0,0,0,1,1,1,1])));b[4]=2;self.assertRaises(CodecError,decode_ab,bytes(b))
if __name__=='__main__':unittest.main(verbosity=2)
