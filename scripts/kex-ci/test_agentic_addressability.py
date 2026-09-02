from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.agentic_addressability import (
    AgentIdentity,
    AgentObserverEvent,
    AgentTask,
    BrainKAgenticFabric,
    TaskState,
)


class AgenticAddressabilityTests(unittest.TestCase):
    def setUp(self):
        self.fabric = BrainKAgenticFabric()
        identity = AgentIdentity.create(
            "braink-agent-casepath",
            "braink-team-casepath",
            ["BRAINK_OPERATOR", "CASEPATH_PUBLISHER"],
            ["casepath.trust-centre.patch"],
            {"service": "app://casepath", "scope": "/your-data.html"},
        )
        self.fabric.registry.register_agent(identity)

    def task(self, task_id="T1"):
        return AgentTask(task_id, "agent://casepath/trust-centre", "casepath.trust-centre.patch",
                         "PATCH", {"patch_id": "CP-TC-20260727-C01"})

    def test_missing_route_is_typed_hole(self):
        r = self.fabric.dispatch(self.task())
        self.assertEqual(r.state, TaskState.DEFERRED)
        self.assertEqual(r.effect["route_state"], "HOLE")

    def test_aperture_without_handler_is_still_routable_hole(self):
        self.fabric.registry.bind("agent://casepath/trust-centre", agent_id="braink-agent-casepath",
                                  capability="casepath.trust-centre.patch",
                                  aperture_id="aperture://casepath/publisher")
        r = self.fabric.dispatch(self.task())
        self.assertEqual(r.failure_reason, "HANDLER_UNBOUND")

    def test_bound_agent_executes_before_public_observer(self):
        self.fabric.registry.bind("agent://casepath/trust-centre", agent_id="braink-agent-casepath",
                                  capability="casepath.trust-centre.patch",
                                  aperture_id="aperture://casepath/publisher")
        self.fabric.registry.register_handler("braink-agent-casepath", "casepath.trust-centre.patch",
            lambda task: {"status":"COMMITTED","logical_target":task.logical_target,
                          "patch_id":task.payload["patch_id"]})
        receipt = self.fabric.dispatch(self.task())
        self.assertEqual(receipt.state, TaskState.EXECUTED)
        tick = self.fabric.carrier_tick
        self.fabric.observe(AgentObserverEvent("observer://public", "agent://casepath/trust-centre",
                                               "PUBLIC_READBACK", {"marker": False}))
        self.assertGreater(self.fabric.carrier_tick, tick)

    def test_revocation_rejects(self):
        self.fabric.registry.bind("agent://casepath/trust-centre", agent_id="braink-agent-casepath",
                                  capability="casepath.trust-centre.patch",
                                  aperture_id="aperture://casepath/publisher")
        self.fabric.registry.revoke("agent://casepath/trust-centre", "AUTHORITY_REVOKED")
        self.assertEqual(self.fabric.dispatch(self.task()).state, TaskState.REJECTED)

    def test_capability_mismatch_becomes_hole(self):
        self.fabric.registry.bind("agent://casepath/trust-centre", agent_id="braink-agent-casepath",
                                  capability="casepath.trust-centre.patch",
                                  aperture_id="aperture://casepath/publisher")
        t = AgentTask("T2", "agent://casepath/trust-centre", "casepath.admin.delete", "DELETE", {})
        self.assertEqual(self.fabric.dispatch(t).effect["route_state"], "HOLE")

    def test_contradiction_reviews_without_erasing_execution(self):
        self.fabric.registry.bind("agent://casepath/trust-centre", agent_id="braink-agent-casepath",
                                  capability="casepath.trust-centre.patch",
                                  aperture_id="aperture://casepath/publisher")
        self.fabric.registry.register_handler("braink-agent-casepath", "casepath.trust-centre.patch",
            lambda task: {"status":"COMMITTED","logical_target":task.logical_target})
        receipt = self.fabric.dispatch(self.task())
        self.fabric.observe(AgentObserverEvent("observer://public", "agent://casepath/trust-centre",
                                               "CONTRADICTION", {"marker": False}))
        self.assertEqual(self.fabric.conflict_review("agent://casepath/trust-centre")["decision"], "REVIEW_REQUIRED")
        self.assertEqual(receipt.state, TaskState.EXECUTED)

    def test_receipt_predecessor_chain(self):
        self.fabric.registry.bind("agent://casepath/trust-centre", agent_id="braink-agent-casepath",
                                  capability="casepath.trust-centre.patch",
                                  aperture_id="aperture://casepath/publisher")
        self.fabric.registry.register_handler("braink-agent-casepath", "casepath.trust-centre.patch",
            lambda task: {"status":"COMMITTED","logical_target":task.logical_target})
        r1 = self.fabric.dispatch(self.task("T1"))
        t2 = AgentTask("T2", "agent://casepath/trust-centre", "casepath.trust-centre.patch", "CONTINUE",
                       {"prior":r1.receipt_root}, predecessor_receipt_root=r1.receipt_root)
        r2 = self.fabric.dispatch(t2)
        self.assertEqual(r2.predecessor_receipt_root, r1.receipt_root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
