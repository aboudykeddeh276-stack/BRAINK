import unittest

from runtime.service_supervisor import (
    EvidenceClassification,
    HealthState,
    IdentityState,
    LifecycleState,
    OwnershipState,
    ProcessIdentity,
    ServiceObservation,
    classify_service,
)


class ServiceSupervisorClassificationTests(unittest.TestCase):
    def identity(self, *, pid=100, start="2026-08-20T10:00:00Z", exe="/usr/local/bin/bitcoind"):
        return ProcessIdentity(pid=pid, start_time=start, executable_path=exe)

    def test_no_observation_is_unobserved_not_absent(self):
        result = classify_service(ServiceObservation(service_id="bitcoin-core"))
        self.assertEqual(result.identity, IdentityState.UNVERIFIED)
        self.assertEqual(result.ownership, OwnershipState.UNKNOWN)
        self.assertEqual(result.health, HealthState.UNKNOWN)
        self.assertEqual(result.lifecycle, LifecycleState.UNOBSERVED)
        self.assertEqual(result.evidence_classification, EvidenceClassification.UNOBSERVED)
        self.assertFalse(result.shutdown_authority)

    def test_explicit_absence_is_distinct_from_unobserved(self):
        result = classify_service(
            ServiceObservation(service_id="bitcoin-core", process_present=False)
        )
        self.assertEqual(result.identity, IdentityState.ABSENT)
        self.assertEqual(result.lifecycle, LifecycleState.ABSENT)
        self.assertEqual(result.evidence_classification, EvidenceClassification.OBSERVED)

    def test_external_healthy_service_is_usable_without_shutdown_authority(self):
        observed = self.identity()
        result = classify_service(
            ServiceObservation(
                service_id="bitcoin-core",
                process_present=True,
                observed_identity=observed,
                started_by_braink=False,
                health=HealthState.HEALTHY,
            )
        )
        self.assertEqual(result.identity, IdentityState.UNVERIFIED)
        self.assertEqual(result.ownership, OwnershipState.EXTERNAL)
        self.assertEqual(result.lifecycle, LifecycleState.RUNNING_HEALTHY)
        self.assertFalse(result.shutdown_authority)

    def test_braink_owned_requires_verified_full_identity(self):
        identity = self.identity()
        result = classify_service(
            ServiceObservation(
                service_id="bitcoin-core",
                expected_identity=identity,
                observed_identity=identity,
                process_present=True,
                started_by_braink=True,
                health=HealthState.HEALTHY,
            )
        )
        self.assertEqual(result.identity, IdentityState.VERIFIED)
        self.assertEqual(result.ownership, OwnershipState.BRAINK_OWNED)
        self.assertTrue(result.shutdown_authority)

    def test_pid_match_with_start_time_change_is_identity_conflict(self):
        expected = self.identity(pid=444, start="2026-08-20T10:00:00Z")
        reused = self.identity(pid=444, start="2026-08-20T11:00:00Z")
        result = classify_service(
            ServiceObservation(
                service_id="bitcoin-core",
                expected_identity=expected,
                observed_identity=reused,
                process_present=True,
                started_by_braink=True,
                health=HealthState.HEALTHY,
            )
        )
        self.assertEqual(result.identity, IdentityState.CONFLICT)
        self.assertEqual(result.ownership, OwnershipState.UNKNOWN)
        self.assertEqual(result.lifecycle, LifecycleState.IDENTITY_CONFLICT)
        self.assertEqual(result.evidence_classification, EvidenceClassification.FAILED)
        self.assertFalse(result.shutdown_authority)

    def test_executable_change_is_identity_conflict(self):
        expected = self.identity(exe="/opt/bitcoin/bin/bitcoind")
        observed = self.identity(exe="/tmp/fake/bitcoind")
        result = classify_service(
            ServiceObservation(
                service_id="bitcoin-core",
                expected_identity=expected,
                observed_identity=observed,
                process_present=True,
                started_by_braink=True,
            )
        )
        self.assertEqual(result.identity, IdentityState.CONFLICT)
        self.assertFalse(result.shutdown_authority)

    def test_explicit_contradiction_fails_closed(self):
        identity = self.identity()
        result = classify_service(
            ServiceObservation(
                service_id="bitcoin-core",
                expected_identity=identity,
                observed_identity=identity,
                process_present=True,
                started_by_braink=True,
                health=HealthState.HEALTHY,
                contradictions=("rpc network does not match expected network",),
            )
        )
        self.assertEqual(result.lifecycle, LifecycleState.IDENTITY_CONFLICT)
        self.assertEqual(result.evidence_classification, EvidenceClassification.FAILED)
        self.assertFalse(result.shutdown_authority)

    def test_health_and_ownership_are_orthogonal(self):
        identity = self.identity()
        result = classify_service(
            ServiceObservation(
                service_id="bitcoin-core",
                expected_identity=identity,
                observed_identity=identity,
                process_present=True,
                started_by_braink=True,
                health=HealthState.SYNCING,
            )
        )
        self.assertEqual(result.ownership, OwnershipState.BRAINK_OWNED)
        self.assertEqual(result.health, HealthState.SYNCING)
        self.assertEqual(result.lifecycle, LifecycleState.RUNNING_SYNCING)

    def test_invalid_absence_plus_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            ServiceObservation(
                service_id="bitcoin-core",
                process_present=False,
                observed_identity=self.identity(),
            )

    def test_classifier_has_no_process_mutation_surface(self):
        import runtime.service_supervisor as module

        prohibited = {"start", "stop", "restart", "kill", "terminate", "popen"}
        exported = {name.lower() for name in dir(module)}
        self.assertTrue(prohibited.isdisjoint(exported))


if __name__ == "__main__":
    unittest.main()
