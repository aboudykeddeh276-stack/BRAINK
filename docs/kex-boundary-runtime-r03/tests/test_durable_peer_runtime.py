import os,sys,tempfile,unittest
from dataclasses import asdict
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','src'))
from durable_peer_runtime import *

class DurablePeerRuntimeTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.mkdtemp();self.c=DurablePeerCluster(self.tmp)
 def test_majority_commit(self):self.assertEqual(self.c.commit('2,2',b'A')[0].generation,1)
 def test_one_peer_down(self):self.c.set_online('n3',False);self.assertEqual(len(self.c.commit('2,2',b'A')[1]),2)
 def test_quorum_loss_fails_closed(self):
  self.c.set_online('n2',False);self.c.set_online('n3',False);self.assertRaises(PeerFault,self.c.commit,'2,2',b'A')
 def test_restart_recovers_fsynced_log(self):self.c.commit('2,2',b'A');self.assertEqual(len(self.c.restart('n2').log),1)
 def test_payload_tamper_rejected(self):
  e=Entry(1,1,'2,2',1,sha(b'A'),None,'n1');env=self.c.nodes['n1'].identity.sign(asdict(e));bad=Envelope(env.sender,{**env.payload,'generation':9},env.signature)
  self.assertRaises(PeerFault,self.c.nodes['n2'].accept,bad,self.c.keys)
 def test_unknown_identity_rejected(self):
  e=Entry(1,1,'2,2',1,sha(b'A'),None,'evil');env=PeerIdentity('evil',b'x').sign(asdict(e));self.assertRaises(PeerFault,self.c.nodes['n2'].accept,env,self.c.keys)
 def test_wal_corruption_detected(self):
  self.c.commit('2,2',b'A');p=self.c.nodes['n2'].wal.path
  with open(p,'a') as f:f.write('{broken')
  self.assertRaises(PeerFault,self.c.restart,'n2')
 def test_reordered_entry_rejected(self):
  e=Entry(2,1,'2,2',1,sha(b'A'),None,'n1');env=self.c.nodes['n1'].identity.sign(asdict(e));self.assertRaises(PeerFault,self.c.nodes['n2'].accept,env,self.c.keys)
 def test_duplicate_entry_rejected(self):
  e,_=self.c.commit('2,2',b'A');env=self.c.nodes['n1'].identity.sign(asdict(e));self.assertRaises(PeerFault,self.c.nodes['n2'].accept,env,self.c.keys)

if __name__=='__main__':unittest.main(verbosity=2)
