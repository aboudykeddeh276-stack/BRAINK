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

 def test_waveform_all_256_roundtrip(self):
  a=GeometryBoundaryAdapter();data=bytes(range(256));f,s,g=a.encode(data,'kex://all',1);self.assertEqual(a.decode(f,s),data)
 def test_original_phase_endpoint_alias_falsified(self):
  self.assertAlmostEqual((TAU*0/255.0)%TAU,(TAU*255/255.0)%TAU,places=12)
 def test_waveform_norm_floor(self):
  a=GeometryBoundaryAdapter();_,_,g=a.encode(bytes(range(256)),'kex://norm',1);self.assertGreaterEqual(min(x.norm for x in g),7.0)
 def test_norm_floor_is_not_component_nonzero_proof(self):
  a=GeometryBoundaryAdapter();_,_,g=a.encode(bytes(range(256)),'kex://components',1);self.assertTrue(any(abs(x.z)<0.04 for x in g))
 def test_waveform_distortion_and_phase_faults(self):
  from dataclasses import replace
  a=GeometryBoundaryAdapter();f,s,g=a.encode(b'abc','kex://fault',1);bad=list(g);bad[0]=replace(bad[0],x=bad[0].x+0.5);self.assertRaises(GeometryViolation,a.engine.verify,bad)
  bads=list(s);bads[1]=replace(bads[1],phase=(bads[1].phase+0.2)%TAU);self.assertRaises(GeometryViolation,a.decode,f,bads)
 def test_0297_is_enforced_bound_not_sync_proof(self):
  a=GeometryBoundaryAdapter();f,s,g=a.encode(b'abc','kex://jitter',1);self.assertRaises(GeometryViolation,a.decode,f,s,0.298)
 def test_waveform_generation_and_reconcile(self):
  a=GeometryBoundaryAdapter();d=WaveformCoordinateDirectory();r=WaveformLayer2Reconciler();f,_,_=a.encode(b'a','kex://x',1);d.commit(f);self.assertRaises(GeometryViolation,d.commit,f);self.assertEqual(r.reconcile(f,None),'MATERIALISE');self.assertEqual(r.reconcile(f,f),'NOOP')
 def test_nonzero_geometry_does_not_make_desync_impossible(self):
  a=GeometryBoundaryAdapter();d1=WaveformCoordinateDirectory();d2=WaveformCoordinateDirectory();f1,_,_=a.encode(b'a','kex://x',1);f2,_,_=a.encode(b'b','kex://x',2);d1.commit(f1);d2.commit(f2);self.assertNotEqual(d1.records['kex://x'].payload_sha256,d2.records['kex://x'].payload_sha256)

if __name__=='__main__':unittest.main(verbosity=2)
