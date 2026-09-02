import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from observer2_federation_r29 import EnvironmentFederation, Observer2Runtime
from observer2_resident_state_r29 import RecursiveComputerProbe
from observer2_federated_control_loop_r29 import Admission, Observer2FederatedControlLoop


class Resident:
    def __init__(self): self.revision = 1
    def snapshot(self): return {"identity": {"computer_id": "A", "lineage": ["A"]}, "revision": self.revision}


class ControlLoopTests(unittest.TestCase):
    def make(self):
        resident = Resident()
        federation = EnvironmentFederation("observer2://control-test")
        federation.register(RecursiveComputerProbe(resident))
        return resident, Observer2FederatedControlLoop(Observer2Runtime(federation=federation))

    def test_denied_candidate_never_calls_actuator_and_still_post_observes(self):
        resident, loop = self.make(); calls=[]
        result = loop.cycle(
            objective="deny-test",
            think=lambda pre: {"op":"increment"},
            mirror=lambda cand,pre: {"candidate":cand,"invariants":False},
            learn=lambda mirror: Admission("REJECT","invariant failed",{"mirror":mirror}),
            actuator=lambda cand: calls.append(cand) or {"ok":True},
            target=lambda execution,comparison: execution["status"]=="EXECUTED",
        )
        self.assertEqual([], calls)
        self.assertEqual("NOT_EXECUTED", result["execution"]["status"])
        self.assertEqual(1, result["pre"]["logical_time"])
        self.assertEqual(2, result["post"]["logical_time"])
        self.assertEqual("RECONCILE", result["continuation"]["next_route"])

    def test_admitted_action_mutates_external_resident_then_post_observer_detects_delta(self):
        resident, loop = self.make(); calls=[]
        def act(cand):
            calls.append(cand); resident.revision += 1; return {"revision":resident.revision}
        result = loop.cycle(
            objective="increment-resident",
            think=lambda pre: {"op":"increment","from":pre["receipts"][0]["payload"]["state"]["revision"]},
            mirror=lambda cand,pre: {"candidate":cand,"invariants":True},
            learn=lambda mirror: Admission("ADMIT","mirror invariants survived",{"root":"mirror"}),
            actuator=act,
            target=lambda execution,comparison: execution["status"]=="EXECUTED" and comparison["changed"],
            continuation={"parent":"R28"},
        )
        self.assertEqual(1, len(calls))
        self.assertEqual("EXECUTED", result["execution"]["status"])
        self.assertTrue(result["comparison"]["changed"])
        self.assertEqual("FOLLOW_SUCCESSOR_STATE", result["continuation"]["next_route"])
        self.assertEqual("R28", result["continuation"]["parent"])
        self.assertEqual(64, len(result["cycle_root"]))

    def test_actuator_exception_is_retained_and_post_observation_still_occurs(self):
        resident, loop = self.make()
        def fail(_): raise RuntimeError("actuator offline")
        result = loop.cycle(
            objective="failure-retention",
            think=lambda pre: {"op":"x"},
            mirror=lambda cand,pre: {"invariants":True},
            learn=lambda mirror: Admission("ADMIT","ok",{}),
            actuator=fail,
            target=lambda execution,comparison: False,
        )
        self.assertEqual("EXECUTION_ERROR", result["execution"]["status"])
        self.assertIn("actuator offline", result["execution"]["error"])
        self.assertEqual(2, result["post"]["logical_time"])
        self.assertEqual("RECONCILE", result["continuation"]["next_route"])

    def test_cycle_root_is_receipt_identity_not_semantic_equivalence_claim(self):
        resident, loop = self.make()
        result = loop.cycle(
            objective="receipt-root",
            think=lambda pre: {"op":"noop"},
            mirror=lambda cand,pre: {"invariants":True},
            learn=lambda mirror: Admission("REJECT","noop",{}),
            actuator=lambda cand: {},
            target=lambda execution,comparison: False,
        )
        self.assertEqual(64, len(result["cycle_root"]))
        self.assertTrue(result["pre"]["environment_root_sha256"])


if __name__ == "__main__": unittest.main(verbosity=2)
