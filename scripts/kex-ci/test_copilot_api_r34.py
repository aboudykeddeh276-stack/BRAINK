import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("KEX_SIGNAL_AUTH_TOKEN", "test-token")
os.environ.setdefault("KEX_SIGNAL_AUTHORITY", "KEDDEH_SYSTEMS")
os.environ.setdefault("KEX_SIGNAL_QUIET", "1")

import runtime.signal_service as signal_service
import runtime.copilot_api as copilot


class CopilotApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        signal_service.STATE_DIR = root / "signal"
        signal_service._RUNTIMES.clear()
        copilot.REGISTRY_PATH = root / "runtime_registry.sqlite"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), signal_service.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        copilot.SIGNAL_BASE = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        signal_service._RUNTIMES.clear()
        self.tmp.cleanup()

    def test_boot_commits_through_signal_service(self):
        result = copilot.boot_runtime()
        self.assertEqual(result["status"], "online")
        self.assertEqual(result["receipt"]["status"], "COMMITTED")
        snapshot = copilot._target_snapshot(copilot.DEFAULT_TARGET)
        self.assertEqual(snapshot["state"]["runtime_status"], "ONLINE")
        self.assertEqual(snapshot["head_sequence"], 1)
        self.assertEqual(snapshot["next_sequence"], 2)

    def test_empty_mesh_does_not_invent_nodes(self):
        result = copilot.ping_mesh()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["registered"], 0)
        self.assertEqual(result["nodes"], [])

    def test_operation_chat_routes_to_signal_manifest(self):
        result = copilot.chat_execute("show operations")
        self.assertEqual(result["route"], "OPERATION_MANIFEST")
        self.assertIn("STATE_PATCH", result["result"]["operations"])
        self.assertIn("CASEPATH_DISPATCH", result["result"]["operations"])

    def test_unmatched_chat_is_explicitly_unbound(self):
        result = copilot.chat_execute("write a novel about the moon")
        self.assertEqual(result["route"], "UNBOUND_CHAT_SEMANTICS")
        self.assertIn("not currently bound", result["reply"])

    def test_state_patch_chat_commits_through_signal_service(self):
        result = copilot.chat_execute("set state mode=ACTIVE")
        self.assertEqual(result["route"], "STATE_PATCH")
        self.assertEqual(result["result"]["status"], "COMMITTED")
        self.assertEqual(copilot._target_snapshot(copilot.DEFAULT_TARGET)["state"]["mode"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
