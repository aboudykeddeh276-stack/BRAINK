import tempfile
import unittest
from pathlib import Path

from runtime.estate_signal_handlers import register_estate_handlers
from runtime.signal_fabric import GENESIS, SignalRequest, SignalRuntime


class EstateSignalHandlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.registry_path = root / "registry.sqlite"
        self.runtime = SignalRuntime(root / "state.json", root / "receipt.json")
        register_estate_handlers(self.runtime)

    def tearDown(self):
        self.tmp.cleanup()

    def compile(self, operation, payload):
        state = self.runtime._read_state()
        previous = self.runtime._previous_receipt()
        if previous == GENESIS:
            seq = 1
        else:
            journal = self.runtime._read_journal()
            seq = max(int(item["sequence"]) for item in journal["receipts"].values()) + 1
        return SignalRequest.compile(
            source="app://braink/workbook",
            target="runtime://kex/virtual-infrastructure",
            operation=operation,
            state=state,
            payload=payload,
            invariants=("state_must_be_object",),
            authority="KEDDEH_SYSTEMS",
            sequence=seq,
            previous_receipt=previous,
        )

    def test_operation_registry_contains_estate_routes(self):
        self.assertTrue({
            "KEX_ACTION",
            "CASEPATH_DISPATCH",
            "WORKBOOK_READ",
            "RUNTIME_REGISTER",
            "RUNTIME_DESIRED_STATE",
        }.issubset(self.runtime.handlers))

    def test_runtime_registry_round_trip_through_signal(self):
        register = self.compile("RUNTIME_REGISTER", {
            "registry_path": str(self.registry_path),
            "runtime": {
                "runtime_id": "runtime://test/alpha",
                "runtime_class": "PROCESS",
                "command_route": "python",
                "argv": ["-m", "example"],
                "desired_state": "STOPPED",
                "observed_state": "DEFINED",
            },
        })
        first = self.runtime.execute(register)
        self.assertEqual(first.status, "COMMITTED")
        self.assertEqual(first.result["last_result"]["runtime_id"], "runtime://test/alpha")

        desired = self.compile("RUNTIME_DESIRED_STATE", {
            "registry_path": str(self.registry_path),
            "runtime_id": "runtime://test/alpha",
            "desired_state": "RUNNING",
        })
        second = self.runtime.execute(desired)
        self.assertEqual(second.result["last_result"]["desired_state"], "RUNNING")
        self.assertEqual(second.previous_receipt, first.receipt_hash)

    def test_kex_action_route_reaches_existing_executor(self):
        req = self.compile("KEX_ACTION", {
            "request": {
                "authority": "KEDDEH_SYSTEMS",
                "actionType": "UNBOUND_TEST_ACTION",
                "target": "test://target",
                "payload": {},
            }
        })
        receipt = self.runtime.execute(req)
        self.assertEqual(receipt.result["last_operation"], "KEX_ACTION")
        self.assertEqual(receipt.result["last_result"]["status"], "ARMED")
        self.assertIn("no local executor", receipt.result["last_result"]["details"]["claimBoundary"])


if __name__ == "__main__":
    unittest.main()
