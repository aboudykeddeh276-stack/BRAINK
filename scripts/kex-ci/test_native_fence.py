from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from modules.kex_wbos.kex_native_fence import (
    Membership, DurableFenceNode, PartitionedFenceCluster, ResourceFenceGate, FenceProposal
)

class NativeFenceTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="kex_native_fence_")
        root = Path(self.td.name)
        self.membership = Membership.create(7, ["Alpha","Beta","Gamma"])
        self.nodes = {
            n: DurableFenceNode(n, root/f"{n}.sqlite3", self.membership)
            for n in self.membership.members
        }
        self.cluster = PartitionedFenceCluster(self.nodes, self.membership)
        self.gate = ResourceFenceGate()

    def tearDown(self):
        self.td.cleanup()

    def test_partition_stale_owner_is_fenced_at_resource(self):
        c1 = self.cluster.acquire("Alpha", "vfs://canonical-head", 0, nonce="A1")
        s1 = self.gate.mutate(c1, {"head":"R1"}, self.membership)
        self.assertEqual(s1["generation"], 1)
        self.cluster.partition([["Alpha"], ["Beta","Gamma"]])
        c2 = self.cluster.acquire("Beta", "vfs://canonical-head", 1, nonce="B2")
        s2 = self.gate.mutate(c2, {"head":"R2"}, self.membership)
        self.assertEqual(s2["generation"], 2)
        with self.assertRaisesRegex(RuntimeError, "STALE_FENCE_REJECTED"):
            self.gate.mutate(c1, {"head":"STALE"}, self.membership)
        self.cluster.heal()
        with self.assertRaisesRegex(RuntimeError, "STALE_FENCE_REJECTED"):
            self.gate.mutate(c1, {"head":"STALE_AFTER_HEAL"}, self.membership)

    def test_minority_partition_cannot_acquire(self):
        self.cluster.partition([["Alpha"], ["Beta","Gamma"]])
        with self.assertRaises(ValueError):
            self.cluster.acquire("Alpha", "agenda://next", 0, nonce="A")

    def test_competing_same_generation_cannot_both_certify(self):
        self.cluster.partition([["Alpha","Beta"], ["Gamma"]])
        x = self.cluster.acquire("Alpha", "resource://x", 0, nonce="X")
        self.assertEqual(x.generation, 1)
        self.cluster.heal()
        with self.assertRaises(ValueError):
            self.cluster.acquire("Gamma", "resource://x", 0, nonce="Y")

    def test_vote_conflict_survives_restart(self):
        p1 = FenceProposal.create(resource="resource://restart", generation=1, previous_generation=0,
                                  owner="Alpha", membership=self.membership, nonce="X")
        self.nodes["Beta"].vote(p1)
        db = self.nodes["Beta"].db_path
        restarted = DurableFenceNode("Beta", db, self.membership)
        p2 = FenceProposal.create(resource="resource://restart", generation=1, previous_generation=0,
                                  owner="Gamma", membership=self.membership, nonce="Y")
        with self.assertRaisesRegex(RuntimeError, "CONFLICTING_VOTE_REJECTED"):
            restarted.vote(p2)

    def test_persistent_replay_high_water(self):
        n = self.nodes["Alpha"]
        self.assertTrue(n.observe_counter("Beta", 10))
        self.assertFalse(n.observe_counter("Beta", 10))
        self.assertFalse(n.observe_counter("Beta", 9))
        self.assertTrue(n.observe_counter("Beta", 11))
        restarted = DurableFenceNode("Alpha", n.db_path, self.membership)
        self.assertFalse(restarted.observe_counter("Beta", 11))
        self.assertTrue(restarted.observe_counter("Beta", 12))

    def test_membership_epoch_root_is_bound(self):
        c1 = self.cluster.acquire("Alpha", "resource://membership", 0)
        newer = Membership.create(8, ["Alpha","Beta","Gamma"])
        with self.assertRaisesRegex(RuntimeError, "STALE_MEMBERSHIP_CERTIFICATE"):
            self.gate.mutate(c1, {"x":1}, newer)

if __name__ == "__main__":
    unittest.main(verbosity=2)
