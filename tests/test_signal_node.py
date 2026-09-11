import unittest

from runtime.signal_node import Signal, SignalKind, SignalNode


class SignalNodeTests(unittest.TestCase):
    def test_trigger_executes_registered_mechanic_once(self):
        calls = []
        node = SignalNode()
        node.register("runtime://braink/core", lambda s: calls.append(s.kind.value) or {"ok": True})
        signal = Signal(SignalKind.TRIGGER, "runtime://braink/core", authority="KEDDEH")
        first = node.dispatch(signal)
        second = node.dispatch(signal)
        self.assertEqual(first.status, "EXECUTED")
        self.assertEqual(first.receipt_hash, second.receipt_hash)
        self.assertEqual(calls, ["TRIGGER"])

    def test_retrigger_is_deliberate_new_activation(self):
        calls = []
        node = SignalNode()
        node.register("runtime://braink/core", lambda s: calls.append(s.kind.value) or {"ok": True})
        node.dispatch(Signal(SignalKind.TRIGGER, "runtime://braink/core", authority="KEDDEH"))
        node.dispatch(Signal(SignalKind.RETRIGGER, "runtime://braink/core", authority="KEDDEH"))
        self.assertEqual(calls, ["TRIGGER", "RETRIGGER"])

    def test_power_reset_returns_target_to_on(self):
        node = SignalNode()
        node.register("runtime://braink/core", lambda s: {"mechanic": "resident"})
        receipt = node.dispatch(Signal(SignalKind.POWER_RESET, "runtime://braink/core", authority="KEDDEH"))
        self.assertEqual(receipt.observed["power_state"], "ON")

    def test_missing_authority_is_denied_without_execution(self):
        calls = []
        node = SignalNode()
        node.register("runtime://braink/core", lambda s: calls.append(1) or {})
        receipt = node.dispatch(Signal(SignalKind.TRIGGER, "runtime://braink/core"))
        self.assertEqual(receipt.status, "DENIED")
        self.assertEqual(calls, [])

    def test_unknown_target_is_unresolved(self):
        node = SignalNode()
        receipt = node.dispatch(Signal(SignalKind.TRIGGER, "runtime://missing", authority="KEDDEH"))
        self.assertEqual(receipt.status, "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
