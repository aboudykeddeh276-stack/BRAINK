import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from observer2_federation_r29 import EnvironmentFederation, Observer2Runtime
from observer2_resident_state_r29 import (
    SelfAddressingRuntimeProbe,
    RecursiveComputerProbe,
    KexCoordinatePlaneProbe,
    compare_federated_frames,
    derive_continuation,
)


class FakeSelfAddressing:
    def __init__(self): self.tick = 2
    def snapshot(self): return {"tick": self.tick, "bindings": {"KEX://A": {"adapter": "memory"}}, "continuations": {}}
    def route(self, *args, **kwargs): raise AssertionError("observer must never call route")
    def checkpoint(self): raise AssertionError("observer must never call checkpoint")


class FakeRecursiveComputer:
    def __init__(self): self.revision = 1
    def snapshot(self): return {"identity": {"computer_id": "A", "lineage": ["A"]}, "revision": self.revision}
    def commit(self): raise AssertionError("observer must never call commit")


class FakeCoordinatePlane:
    def __init__(self): self.geometry = [297, 297, 297]
    def snapshot(self): return {"dimensions": self.geometry, "wrap": "((n-1) mod dimension)+1", "zero_input_rejected": True}
    def dispatch(self): raise AssertionError("observer must never call dispatch")


class ResidentStateTests(unittest.TestCase):
    def federation(self, a, r, k):
        f = EnvironmentFederation("observer2://resident-test")
        f.register(SelfAddressingRuntimeProbe(a))
        f.register(RecursiveComputerProbe(r))
        f.register(KexCoordinatePlaneProbe(k))
        return f

    def test_resident_probes_use_snapshot_only(self):
        a, r, k = FakeSelfAddressing(), FakeRecursiveComputer(), FakeCoordinatePlane()
        frame = Observer2Runtime(federation=self.federation(a, r, k)).observe()
        self.assertEqual({"braink-self-addressing-runtime", "braink-recursive-computer", "kex-coordinate-plane"}, {x.substrate for x in frame.receipts})
        self.assertEqual({"OBSERVED"}, {x.status for x in frame.receipts})

    def test_identical_payloads_compare_unchanged_despite_new_sample_times(self):
        a, r, k = FakeSelfAddressing(), FakeRecursiveComputer(), FakeCoordinatePlane()
        runtime = Observer2Runtime(federation=self.federation(a, r, k))
        before = runtime.observe(); after = runtime.observe()
        cmp = compare_federated_frames(before, after)
        self.assertFalse(cmp["changed"])
        self.assertTrue(all(not d["changed"] for d in cmp["environment_deltas"]))

    def test_one_resident_mutation_is_localised_to_its_environment_delta(self):
        a, r, k = FakeSelfAddressing(), FakeRecursiveComputer(), FakeCoordinatePlane()
        runtime = Observer2Runtime(federation=self.federation(a, r, k))
        before = runtime.observe(); r.revision = 2; after = runtime.observe()
        cmp = compare_federated_frames(before, after)
        changed = [d for d in cmp["environment_deltas"] if d["changed"]]
        self.assertEqual(1, len(changed))
        self.assertEqual("env://braink/recursive-computer", changed[0]["environment_id"])

    def test_continuation_follows_successor_only_when_target_satisfied(self):
        a, r, k = FakeSelfAddressing(), FakeRecursiveComputer(), FakeCoordinatePlane()
        runtime = Observer2Runtime(federation=self.federation(a, r, k))
        before = runtime.observe(); r.revision = 2; after = runtime.observe(); cmp = compare_federated_frames(before, after)
        good = derive_continuation(before, after, cmp, target_satisfied=True, prior={"parent": "R28"})
        bad = derive_continuation(before, after, cmp, target_satisfied=False)
        self.assertEqual("FOLLOW_SUCCESSOR_STATE", good["next_route"])
        self.assertEqual("R28", good["parent"])
        self.assertEqual("RECONCILE", bad["next_route"])

    def test_observer_identity_change_is_rejected(self):
        a, r, k = FakeSelfAddressing(), FakeRecursiveComputer(), FakeCoordinatePlane()
        before = Observer2Runtime(federation=self.federation(a, r, k)).observe()
        f2 = EnvironmentFederation("observer2://other")
        f2.register(SelfAddressingRuntimeProbe(a))
        after = Observer2Runtime(federation=f2).observe()
        with self.assertRaises(ValueError): compare_federated_frames(before, after)


if __name__ == "__main__": unittest.main(verbosity=2)
