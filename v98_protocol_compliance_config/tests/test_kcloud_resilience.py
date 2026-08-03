import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.keddeh_kcloud_resilience import (
    CircuitBreaker,
    CircuitState,
    Criticality,
    FailureLedger,
    FailureRecord,
    HealthState,
    KCloudAdapter,
    MeshNodeStatus,
    NodeHealth,
    deployment_gate,
    verify_manifest_integrity,
)


class KCloudResilienceTests(unittest.TestCase):
    def test_integrity_readback_accepts_exact_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "k-app.manifest.json"
            path.write_text(
                json.dumps({
                    "applicationId": "kex.workstation.core",
                    "version": "1.2.0",
                }),
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertTrue(deployment_gate(path, digest).valid)

    def test_integrity_readback_blocks_tampered_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "k-app.manifest.json"
            path.write_text(
                json.dumps({
                    "applicationId": "kex.workstation.core",
                    "version": "1.2.0",
                }),
                encoding="utf-8",
            )
            result = verify_manifest_integrity(path, "0" * 64)
            self.assertFalse(result.valid)
            with self.assertRaises(RuntimeError):
                deployment_gate(path, "0" * 64)

    def test_failure_ledger_reconciles_only_after_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = FailureLedger(Path(td) / "failure.ledger")
            record = FailureRecord(
                "f1",
                "mesh",
                "MESH_REGISTRATION",
                Criticality.DEFERRED_COMMIT,
                "unavailable",
                ["mesh-registration"],
                "DEFERRED_COMMIT",
                "local-outbox",
                ["mesh healthy"],
            )
            ledger.record_failure(record)
            ledger.defer_work("f1", {"package": "v1"})
            with self.assertRaises(RuntimeError):
                ledger.reconcile_deferred("f1", lambda work: work)
            ledger.mark_recovered("f1", {"probe": "pass"})
            self.assertEqual(
                ledger.reconcile_deferred("f1", lambda work: work["package"]),
                ["v1"],
            )
            self.assertEqual(ledger.open_failures(), {})

    def test_health_state_degrades_ui_on_dependency_failure(self):
        monitor = HealthState(stale_after_seconds=60)
        monitor.update(MeshNodeStatus(
            "node-1",
            NodeHealth.HEALTHY,
            {"mesh": NodeHealth.FAILED},
            True,
            100.0,
        ))
        snapshot = monitor.snapshot(now=110.0)
        self.assertEqual(snapshot["ui_state"], "degraded")
        self.assertTrue(snapshot["nodes"]["node-1"]["core_semantic_validity"])

    def test_health_state_marks_stale(self):
        monitor = HealthState(stale_after_seconds=5)
        monitor.update(MeshNodeStatus(
            "node-1",
            NodeHealth.HEALTHY,
            {},
            True,
            100.0,
        ))
        self.assertEqual(
            monitor.snapshot(now=106.0)["nodes"]["node-1"]["health"],
            "STALE",
        )

    def test_circuit_breaker_opens_and_uses_fallback(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10)

        def fail():
            raise OSError("down")

        self.assertEqual(breaker.call(fail, lambda: "fallback", now=0), "fallback")
        self.assertEqual(breaker.call(fail, lambda: "fallback", now=1), "fallback")
        self.assertEqual(breaker.state, CircuitState.OPEN)
        self.assertEqual(
            breaker.call(lambda: "should-not-run", lambda: "fallback", now=2),
            "fallback",
        )

    def test_circuit_breaker_half_open_recovers(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=5)
        breaker.call(
            lambda: (_ for _ in ()).throw(OSError()),
            lambda: "fallback",
            now=0,
        )
        self.assertEqual(
            breaker.call(lambda: "ok", lambda: "fallback", now=6),
            "ok",
        )
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    def test_adapter_isolates_mesh_and_telemetry_failures(self):
        adapter = KCloudAdapter(
            CircuitBreaker(1, 5),
            CircuitBreaker(1, 5),
        )
        mesh = adapter.register_package(
            lambda: (_ for _ in ()).throw(ConnectionError()),
            lambda: "queued",
        )
        telemetry = adapter.publish_telemetry(
            lambda: (_ for _ in ()).throw(ConnectionError()),
            lambda: "local-outbox",
        )
        self.assertEqual(mesh, "queued")
        self.assertEqual(telemetry, "local-outbox")


if __name__ == "__main__":
    unittest.main()
