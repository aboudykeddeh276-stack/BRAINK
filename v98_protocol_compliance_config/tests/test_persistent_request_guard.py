import tempfile
import unittest
from pathlib import Path

from src.keddeh_persistent_request_guard import GuardError, PersistentRequestGuard, guard_headers


class PersistentRequestGuardTests(unittest.TestCase):
    def new_guard(self, directory: str, **kwargs):
        return PersistentRequestGuard(Path(directory) / "guard-state.json", **kwargs)

    def test_valid_request_and_restart_persistent_replay_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = self.new_guard(directory)
            decision = guard.check_and_consume("agent-a", "request-1", 100, now=100)
            self.assertTrue(decision.accepted)

            restarted = self.new_guard(directory)
            with self.assertRaises(GuardError) as context:
                restarted.check_and_consume("agent-a", "request-1", 100, now=101)
            self.assertEqual(context.exception.status, 409)

    def test_missing_request_identifier_returns_428(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = self.new_guard(directory)
            with self.assertRaises(GuardError) as context:
                guard.check_and_consume("agent-a", "", 100, now=100)
            self.assertEqual(context.exception.status, 428)

    def test_stale_request_returns_408(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = self.new_guard(directory, freshness_seconds=5)
            with self.assertRaises(GuardError) as context:
                guard.check_and_consume("agent-a", "request-1", 90, now=100)
            self.assertEqual(context.exception.status, 408)

    def test_rate_limit_is_independent_per_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = self.new_guard(
                directory, window_seconds=60, max_mutations_per_window=1
            )
            guard.check_and_consume("agent-a", "request-a-1", 100, now=100)
            with self.assertRaises(GuardError) as context:
                guard.check_and_consume("agent-a", "request-a-2", 101, now=101)
            self.assertEqual(context.exception.status, 429)
            self.assertGreaterEqual(context.exception.retry_after, 1)

            second_agent = guard.check_and_consume(
                "agent-b", "request-b-1", 101, now=101
            )
            self.assertTrue(second_agent.accepted)

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "guard-state.json"
            state_path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                PersistentRequestGuard(state_path)

    def test_authenticated_status_projection_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = self.new_guard(directory)
            status = guard.status(now=100)
            self.assertEqual(status["state"], "HEALTHY")
            self.assertTrue(status["persistent"])
            self.assertIn("tracked_request_ids", status)
            self.assertIn("tracked_agents", status)

    def test_header_parser(self):
        request_id, timestamp = guard_headers(
            {
                "x-kex-request-id": "request-1",
                "x-kex-request-timestamp": "100.5",
            }
        )
        self.assertEqual(request_id, "request-1")
        self.assertEqual(timestamp, 100.5)


if __name__ == "__main__":
    unittest.main()
