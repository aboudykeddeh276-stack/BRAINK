import unittest

from runtime.instance_registry import InstanceRegistry


class InstanceRegistryTests(unittest.TestCase):
    def test_registration_and_repeatable_state_hash(self):
        a = InstanceRegistry()
        b = InstanceRegistry()
        self.assertEqual(a.register("worker-1", "worker", {"lane": 1})["status"], "registered")
        self.assertEqual(b.register("worker-1", "worker", {"lane": 1})["status"], "registered")
        self.assertEqual(a.state_hash(), b.state_hash())

    def test_directive_and_restart_accounting(self):
        registry = InstanceRegistry()
        registry.register("worker-1", "worker")
        result = registry.apply_directive("worker-1", "set_max_restart_attempts", {"attempts": 2})
        self.assertEqual(result["status"], "directive_applied")
        self.assertFalse(registry.record_restart_attempt("worker-1")["limit_reached"])
        self.assertTrue(registry.record_restart_attempt("worker-1")["limit_reached"])

    def test_invalid_and_unknown_directives_are_non_mutating(self):
        registry = InstanceRegistry()
        before = registry.state_hash()
        result = registry.apply_directive("missing", "force_restart", {})
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(before, registry.state_hash())
        registry.register("worker-1", "worker")
        before = registry.state_hash()
        result = registry.apply_directive("worker-1", "set_heartbeat_interval", {"interval": 0})
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(before, registry.state_hash())


if __name__ == "__main__":
    unittest.main()
