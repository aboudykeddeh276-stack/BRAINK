import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from runtime.signal_fabric import GENESIS, SignalRequest, SignalRuntime, canonical_json, default_mutation_handler, sha256_hex


class SignalFabricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state_path = root / "state.json"
        self.receipt_path = root / "receipt.json"
        self.state_path.write_text("{}", encoding="utf-8")
        self.runtime = SignalRuntime(self.state_path, self.receipt_path)
        self.runtime.register("STATE_PATCH", default_mutation_handler)

    def tearDown(self):
        self.tmp.cleanup()

    def compile(self, state=None, seq=1, previous=GENESIS):
        return SignalRequest.compile(
            source="app://braink/workbook",
            target="runtime://kex/virtual-infrastructure",
            operation="STATE_PATCH",
            state={} if state is None else state,
            payload={"patch": {"status": "ACTIVE", "revision": seq}},
            invariants=("state_must_be_object", "no_null_state"),
            authority="KEDDEH_SYSTEMS",
            sequence=seq,
            previous_receipt=previous,
        )

    def test_compile_is_deterministic(self):
        a = self.compile()
        b = self.compile()
        self.assertEqual(a.proof_root, b.proof_root)
        self.assertEqual(a.signal_id, b.signal_id)

    def test_execute_commits_and_receipts(self):
        req = self.compile()
        receipt = self.runtime.execute(req)
        self.assertEqual(receipt.status, "COMMITTED")
        self.assertEqual(receipt.phase, "RECEIPT")
        persisted = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "ACTIVE")
        self.assertEqual(receipt.state_hash_after, sha256_hex(canonical_json(persisted)))

    def test_payload_tamper_is_rejected(self):
        req = self.compile()
        bad = replace(req, compiled_payload={"patch": {"status": "TAMPERED"}})
        with self.assertRaisesRegex(ValueError, "SIGNAL_INTEGRITY_FAILURE"):
            self.runtime.execute(bad)

    def test_stale_state_is_rejected(self):
        req = self.compile(state={"not": "current"})
        with self.assertRaisesRegex(ValueError, "STATE_PRECONDITION_FAILED"):
            self.runtime.execute(req)

    def test_unbound_operation_is_rejected(self):
        req = SignalRequest.compile(
            source="app://casepath",
            target="runtime://kex/virtual-infrastructure",
            operation="NOT_BOUND",
            state={}, payload={}, invariants=(), authority="KEDDEH_SYSTEMS", sequence=1,
        )
        with self.assertRaisesRegex(KeyError, "UNBOUND_OPERATION"):
            self.runtime.execute(req)

    def test_receipt_chain_changes_next_proof(self):
        first = self.compile()
        receipt = self.runtime.execute(first)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        second = self.compile(state=state, seq=2, previous=sha256_hex(self.receipt_path.read_bytes()))
        self.assertNotEqual(first.proof_root, second.proof_root)
        second_receipt = self.runtime.execute(second)
        self.assertEqual(second_receipt.sequence, 2)


if __name__ == "__main__":
    unittest.main()
