from __future__ import annotations
import dataclasses,tempfile,unittest
from pathlib import Path
from modules.kex_wbos.kex_native_fence_v2 import NodeKey,Membership,DurableFenceNode,PartitionedFenceCluster,ResourceFenceGate

class NativeFenceV2Tests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(prefix='kex_fence_v2_'); root=Path(self.td.name)
        self.keys={n:NodeKey.generate(n) for n in ('Alpha','Beta','Gamma')}
        self.membership=Membership.create(11,[k.member() for k in self.keys.values()])
        self.nodes={n:DurableFenceNode(self.keys[n],root/f'{n}.sqlite3',self.membership) for n in self.keys}
        self.cluster=PartitionedFenceCluster(self.nodes,self.keys,self.membership); self.gate=ResourceFenceGate()
    def tearDown(self): self.td.cleanup()
    def test_signed_certificate_and_resource_verification(self):
        c=self.cluster.acquire('Alpha','vfs://head',0,nonce='a1'); self.assertEqual(self.gate.mutate(c,{'head':'R1'},self.membership)['generation'],1)
    def test_forged_vote_signature_rejected(self):
        c=self.cluster.acquire('Alpha','res://x',0); bad=dataclasses.replace(c.votes[0],signature_b64='AA=='); forged=dataclasses.replace(c,votes=(bad,)+c.votes[1:])
        with self.assertRaises(Exception): self.gate.mutate(forged,{'x':1},self.membership)
    def test_forged_certificate_root_rejected(self):
        c=self.cluster.acquire('Alpha','res://root',0); forged=dataclasses.replace(c,certificate_root='0'*64)
        with self.assertRaisesRegex(RuntimeError,'CERTIFICATE_ROOT_INVALID'): self.gate.mutate(forged,{'x':1},self.membership)
    def test_stale_owner_rejected_after_majority_partition_advances(self):
        c1=self.cluster.acquire('Alpha','res://partition',0,nonce='old'); self.gate.mutate(c1,{'v':1},self.membership)
        self.cluster.partition([['Alpha'],['Beta','Gamma']]); c2=self.cluster.acquire('Beta','res://partition',1,nonce='new'); self.gate.mutate(c2,{'v':2},self.membership)
        with self.assertRaisesRegex(RuntimeError,'STALE_FENCE_REJECTED'): self.gate.mutate(c1,{'v':'stale'},self.membership)
    def test_minority_cannot_certify(self):
        self.cluster.partition([['Alpha'],['Beta','Gamma']])
        with self.assertRaises(ValueError): self.cluster.acquire('Alpha','res://minority',0)
    def test_replay_high_water_persists_restart(self):
        n=self.nodes['Alpha']; self.assertTrue(n.observe_counter('Beta',5)); self.assertFalse(n.observe_counter('Beta',5))
        restarted=DurableFenceNode(self.keys['Alpha'],n.db_path,self.membership); self.assertFalse(restarted.observe_counter('Beta',5)); self.assertTrue(restarted.observe_counter('Beta',6))

if __name__=='__main__': unittest.main(verbosity=2)
