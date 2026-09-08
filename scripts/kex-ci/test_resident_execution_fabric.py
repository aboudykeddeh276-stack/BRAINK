#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.orchestration.durable_execution_r5 import ReplayError, StaleEpochError
from enterprise.orchestration.resident_execution_fabric import ResidentExecutionFabric, RoutePolicyError
from runtime.runtime_route_registry import DEFAULT_ROUTES


class ResidentExecutionFabricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.key = b"K" * 32
        self.routes_before = dict(DEFAULT_ROUTES)
        DEFAULT_ROUTES.clear()
        DEFAULT_ROUTES.update({
            "test-pass": {
                "runtime_id": "runtime://test/pass",
                "runtime_class": "ONE_SHOT_JOB",
                "argv": [sys.executable, "-c", "import json;print(json.dumps({'observed':'PASS'}))"],
                "dependencies": [], "health_endpoint": None,
            },
            "test-fail": {
                "runtime_id": "runtime://test/fail",
                "runtime_class": "ONE_SHOT_JOB",
                "argv": [sys.executable, "-c", "import sys;print('intentional failure');sys.exit(7)"],
                "dependencies": [], "health_endpoint": None,
            },
            "test-service": {
                "runtime_id": "runtime://test/service",
                "runtime_class": "PROCESS",
                "argv": [sys.executable, "-c", "import time;time.sleep(30)"],
                "dependencies": [], "health_endpoint": None,
            },
        })
        self.fabric = ResidentExecutionFabric(self.root, self.state, self.key)

    def tearDown(self):
        try:
            for spec in list(DEFAULT_ROUTES.values()):
                rid = spec["runtime_id"]
                proc = self.fabric._processes.get(rid)
                if proc:
                    proc.stop(timeout=0.2)
        finally:
            DEFAULT_ROUTES.clear()
            DEFAULT_ROUTES.update(self.routes_before)
            self.tmp.cleanup()

    def envelope(self, work_id: str, route: str = "test-pass", operation: str = "RUN_ONCE", epoch: int = 1):
        return self.fabric.sign({
            "work_id": work_id,
            "correlation_id": "corr-" + work_id,
            "actor": {"type": "TEST_AUTHORITY", "id": "kex-ci"},
            "sector": "runtime",
            "route": route,
            "operation": operation,
            "continuation": {"epoch": epoch, "status": "ADMITTED"},
            "carrier": "test://local",
        })

    def test_registered_job_executes_and_returns_rooted_proof(self):
        result = self.fabric.dispatch(self.envelope("work-pass"))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["observed"]["returncode"], 0)
        self.assertEqual(len(result["proof"]), 64)
        persisted = self.fabric.journal.get("work-pass")
        self.assertEqual(persisted["state"], "COMPLETED")
        self.assertEqual(persisted["proof_root"], result["proof"])
        self.assertEqual([e["state"] for e in self.fabric.journal.events("work-pass")], ["ADMITTED", "EXECUTING", "COMPLETED"])

    def test_same_signed_envelope_cannot_replay(self):
        envelope = self.envelope("work-replay")
        self.fabric.dispatch(envelope)
        with self.assertRaises(ReplayError):
            self.fabric.dispatch(envelope)

    def test_stale_epoch_is_fenced_even_with_fresh_nonce(self):
        self.fabric.dispatch(self.envelope("work-epoch", epoch=1))
        fresh = self.envelope("work-epoch", epoch=1)
        with self.assertRaises(StaleEpochError):
            self.fabric.dispatch(fresh)

    def test_unregistered_route_is_rejected_before_execution(self):
        envelope = self.fabric.sign({
            "work_id": "work-injection",
            "actor": {"type": "TEST_AUTHORITY"},
            "sector": "runtime",
            "route": "../../bin/sh",
            "operation": "RUN_ONCE",
            "continuation": {"epoch": 1, "status": "ADMITTED"},
        })
        with self.assertRaises(RoutePolicyError):
            self.fabric.dispatch(envelope)
        self.assertIsNone(self.fabric.journal.get("work-injection"))

    def test_failed_registered_job_is_not_promoted_and_is_journaled(self):
        with self.assertRaises(RuntimeError):
            self.fabric.dispatch(self.envelope("work-fail", route="test-fail"))
        persisted = self.fabric.journal.get("work-fail")
        self.assertEqual(persisted["state"], "FAILED")
        self.assertIn("registered job failed", persisted["failure"])
        self.assertIsNone(persisted["proof_root"])

    def test_managed_runtime_lifecycle_updates_registry(self):
        started = self.fabric.dispatch(self.envelope("work-start", route="test-service", operation="START_RUNTIME", epoch=1))
        self.assertTrue(started["observed"]["alive"])
        readback = self.fabric.dispatch(self.envelope("work-readback", route="test-service", operation="READBACK_RUNTIME", epoch=1))
        self.assertTrue(readback["observed"]["process"]["alive"])
        stopped = self.fabric.dispatch(self.envelope("work-stop", route="test-service", operation="STOP_RUNTIME", epoch=1))
        self.assertFalse(stopped["observed"]["alive"])
        registered = self.fabric.registry.get("runtime://test/service")
        self.assertEqual(registered["desired_state"], "STOPPED")
        self.assertEqual(registered["observed_state"], "STOPPED")

    def test_envelope_tamper_invalidates_root_before_signature_is_trusted(self):
        envelope = self.envelope("work-tamper")
        envelope["operation"] = "DESCRIBE_ROUTE"
        with self.assertRaises(Exception) as ctx:
            self.fabric.dispatch(envelope)
        self.assertIn("envelope root mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
