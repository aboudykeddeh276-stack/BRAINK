import unittest

from observer2_runtime.kernel import KexMicroKernelCore, ToroidalCoordinate


class Observer2Tests(unittest.TestCase):
    def test_coordinate_is_immutable(self):
        coord = ToroidalCoordinate(1, 2, 3)
        with self.assertRaises(AttributeError):
            coord._x = 9

    def test_successful_signal_has_pre_post_delta_and_continuation(self):
        kernel = KexMicroKernelCore("test-anchor")
        result = kernel.orchestrate_signal(
            "WEB_PLANE",
            "APK_PLANE",
            "OPEN_PACKAGE",
            {"PACKAGE_ID": "au.com.keddeh.test"},
        )
        self.assertEqual(result["STATUS"], "SIGNAL_PROCESSED")
        record = result["LINEAGE_RECORD"]
        self.assertTrue(record["ADMISSION"]["ADMITTED"])
        self.assertTrue(record["ACTUATION"]["ACCEPTED"])
        self.assertTrue(record["ENVIRONMENT_DELTA"]["CHANGED"])
        self.assertEqual(record["CONTINUATION"]["ACTION"], "FOLLOW_CREATED_DESCENDANTS")
        self.assertFalse(record["MIRROR_CANDIDATE"]["AUTHORITATIVE"])

    def test_failed_actuator_does_not_mutate_observed_state(self):
        kernel = KexMicroKernelCore("test-anchor")
        before = kernel._observer.observe("APK_PLANE", kernel._execution_planes["APK_PLANE"]).state_hash
        result = kernel.orchestrate_signal("WEB_PLANE", "APK_PLANE", "OPEN_PACKAGE", {})
        after = kernel._observer.observe("APK_PLANE", kernel._execution_planes["APK_PLANE"]).state_hash
        self.assertEqual(before, after)
        self.assertFalse(result["LINEAGE_RECORD"]["ACTUATION"]["ACCEPTED"])
        self.assertFalse(result["LINEAGE_RECORD"]["ENVIRONMENT_DELTA"]["CHANGED"])
        self.assertEqual(result["LINEAGE_RECORD"]["CONTINUATION"]["ACTION"], "RESOLVE_ACTUATOR_FAILURE")

    def test_repeatable_initial_proof(self):
        a = KexMicroKernelCore("same-anchor").generate_deterministic_proof()
        b = KexMicroKernelCore("same-anchor").generate_deterministic_proof()
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
