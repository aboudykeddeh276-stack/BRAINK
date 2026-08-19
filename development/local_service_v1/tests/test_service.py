import json
import tempfile
import unittest
from pathlib import Path

from development.local_service_v1.braink_service import BRAINKService, AuthorizationError


class LocalBRAINKServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "evidence.jsonl"
        self.service = BRAINKService(self.ledger)

    def tearDown(self):
        self.tmp.cleanup()

    def test_end_to_end_tool_evidence_is_used_for_continuation(self):
        response = self.service.respond({"message": "diagnose runtime"})
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["skill"], "runtime_diagnostic")
        self.assertEqual(response["tool"], "runtime.identity")
        trace = self.service.trace(response["transaction_id"])
        actions = [event["action"] for event in trace]
        self.assertEqual(actions, [
            "request_received", "context_resolved", "skill_selected",
            "authorization_decision", "tool_started", "tool_result",
            "inference_resumed", "response_emitted"
        ])
        tool_result = next(e["data"]["result"] for e in trace if e["action"] == "tool_result")
        resumed = next(e["data"]["tool_evidence"] for e in trace if e["action"] == "inference_resumed")
        self.assertEqual(tool_result, resumed)
        self.assertIn(tool_result["runtime"], response["response"])

    def test_unauthorized_tool_never_starts(self):
        with self.assertRaises(AuthorizationError):
            self.service.respond({"message": "delete everything", "requested_tool": "shell.exec"})
        events = [json.loads(line) for line in self.ledger.read_text().splitlines()]
        self.assertNotIn("tool_started", [event["action"] for event in events])

    def test_malformed_request_rejected_before_inference(self):
        with self.assertRaises(ValueError):
            self.service.respond({"message": ""})
        self.assertFalse(self.ledger.exists())


if __name__ == "__main__":
    unittest.main()
