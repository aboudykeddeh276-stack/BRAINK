import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from observer2_federation_r29 import CallableProbe, EnvironmentFederation, Observer2Runtime
from braink_recursive_operator_r29 import EvidenceOnlyActionLane, RecursiveObserverOperator


class Observer2FederationR29Tests(unittest.TestCase):
    def test_legacy_single_root_remains_supported(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "alpha.txt").write_text("A")
            runtime = Observer2Runtime(root=td)
            frame = runtime.observe({"route": "legacy"})
            self.assertEqual(1, len(frame.receipts))
            self.assertEqual("OBSERVED", frame.receipts[0].status)
            self.assertEqual("legacy", frame.continuation["route"])

    def test_one_observer_federates_distinct_substrates(self):
        f = EnvironmentFederation("observer2://test")
        f.register(CallableProbe(lambda: {"head": "abc"}, environment_id="env://repo", substrate="git", probe_id="probe://repo"))
        f.register(CallableProbe(lambda: {"status": 200}, environment_id="env://edge", substrate="http", probe_id="probe://edge"))
        frame = f.sample()
        self.assertEqual("observer2://test", frame.observer_id)
        self.assertEqual({"env://repo", "env://edge"}, {r.environment_id for r in frame.receipts})
        self.assertEqual(64, len(frame.environment_root_sha256))

    def test_probe_failure_is_evidence_not_absence(self):
        def fail():
            raise RuntimeError("offline")
        f = EnvironmentFederation()
        f.register(CallableProbe(fail, environment_id="env://remote", substrate="http", probe_id="probe://remote"))
        r = f.sample().receipts[0]
        self.assertEqual("UNAVAILABLE", r.status)
        self.assertIn("offline", r.error)

    def test_probe_mutation_surface_is_rejected(self):
        class BadProbe:
            probe_id = "probe://bad"
            environment_id = "env://bad"
            substrate = "bad"
            def sample(self, observer_id): return {}
            def mutate(self): return None
        f = EnvironmentFederation()
        with self.assertRaises(TypeError):
            f.register(BadProbe())

    def test_evidence_lane_has_no_actuation_surface(self):
        lane = EvidenceOnlyActionLane()
        self.assertFalse(hasattr(lane, "actuate"))
        self.assertFalse(hasattr(lane, "mutate"))
        self.assertFalse(hasattr(lane, "write"))

    def test_recursive_operator_returns_successor_continuation(self):
        f = EnvironmentFederation("observer2://operator")
        f.register(CallableProbe(lambda: {"revision": 29}, environment_id="env://resident", substrate="resident", probe_id="probe://resident"))
        op = RecursiveObserverOperator(Observer2Runtime(federation=f))
        result = op.cycle(objective="reconcile", recommendation="promote-proven-delta", continuation={"parent": "R28"})
        self.assertEqual("FOLLOW_SUCCESSOR_STATE", result["continuation"]["next_route"])
        self.assertEqual("EVIDENCE_ONLY_NO_ACTUATION", result["evidence_action"]["authority"])
        self.assertEqual("R28", result["continuation"]["parent"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
