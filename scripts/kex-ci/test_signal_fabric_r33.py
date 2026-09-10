import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

from runtime.signal_fabric import GENESIS, SignalRequest, SignalRuntime, canonical_json, default_mutation_handler, sha256_hex


class SignalFabricTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.runtime = SignalRuntime(root / "state.json", root / "receipt.json")
        self.runtime.register("STATE_PATCH", default_mutation_handler)

    def tearDown(self):
        self.tmp.cleanup()

    def compile(self, state=None, seq=1, previous=GENESIS, invariants=("state_must_be_object", "no_null_state")):
        return SignalRequest.compile(
            source="app://braink/workbook",
            target="runtime://kex/virtual-infrastructure",
            operation="STATE_PATCH",
            state={} if state is None else state,
            payload={"patch": {"status": "ACTIVE", "revision": seq}},
            invariants=invariants,
            authority="KEDDEH_SYSTEMS",
            sequence=seq,
            previous_receipt=previous,
        )

    def test_compile_is_deterministic(self):
        a = self.compile()
        b = self.compile()
        self.assertEqual(a.proof_root, b.proof_root)
        self.assertEqual(a.signal_id, b.signal_id)

    def test_execute_commits_state_and_receipt_in_one_journal(self):
        receipt = self.runtime.execute(self.compile())
        journal = json.loads(self.runtime.journal_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt.status, "COMMITTED")
        self.assertEqual(journal["state"]["status"], "ACTIVE")
        self.assertEqual(journal["head_receipt"], receipt.receipt_hash)
        self.assertEqual(journal["receipts"][receipt.signal_id]["receipt_hash"], receipt.receipt_hash)
        self.assertEqual(receipt.state_hash_after, sha256_hex(canonical_json(journal["state"])))

    def test_payload_tamper_is_rejected(self):
        req = self.compile()
        bad = replace(req, compiled_payload={"patch": {"status": "TAMPERED"}})
        with self.assertRaisesRegex(ValueError, "SIGNAL_INTEGRITY_FAILURE"):
            self.runtime.execute(bad)

    def test_stale_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "STATE_PRECONDITION_FAILED"):
            self.runtime.execute(self.compile(state={"not": "current"}))

    def test_unbound_operation_is_rejected(self):
        req = SignalRequest.compile(
            source="app://casepath", target="runtime://kex/virtual-infrastructure", operation="NOT_BOUND",
            state={}, payload={}, invariants=(), authority="KEDDEH_SYSTEMS", sequence=1,
        )
        with self.assertRaisesRegex(KeyError, "UNBOUND_OPERATION"):
            self.runtime.execute(req)

    def test_unknown_invariant_is_rejected_at_compile(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_INVARIANT"):
            self.compile(invariants=("pretend_verified",))

    def test_receipt_chain_uses_receipt_hash(self):
        first = self.runtime.execute(self.compile())
        state = self.runtime._read_state()
        second = self.compile(state=state, seq=2, previous=first.receipt_hash)
        second_receipt = self.runtime.execute(second)
        self.assertEqual(second_receipt.previous_receipt, first.receipt_hash)

    def test_duplicate_signal_returns_cached_receipt(self):
        req = self.compile()
        first = self.runtime.execute(req)
        second = self.runtime.execute(req)
        self.assertEqual(first.receipt_hash, second.receipt_hash)
        self.assertEqual(self.runtime._read_state()["revision"], 1)

    def test_concurrent_same_precondition_allows_only_one_distinct_transition(self):
        current = self.runtime._read_state()
        a = SignalRequest.compile(source="a", target="t", operation="STATE_PATCH", state=current,
            payload={"patch":{"winner":"a"}}, invariants=("state_must_be_object",), authority="KEDDEH_SYSTEMS", sequence=1)
        b = SignalRequest.compile(source="b", target="t", operation="STATE_PATCH", state=current,
            payload={"patch":{"winner":"b"}}, invariants=("state_must_be_object",), authority="KEDDEH_SYSTEMS", sequence=1)
        outcomes=[]
        def run(req):
            try:
                outcomes.append(("ok", self.runtime.execute(req).signal_id))
            except Exception as exc:
                outcomes.append(("err", type(exc).__name__))
        t1=threading.Thread(target=run,args=(a,)); t2=threading.Thread(target=run,args=(b,))
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(sum(1 for kind,_ in outcomes if kind=="ok"),1)
        self.assertEqual(sum(1 for kind,_ in outcomes if kind=="err"),1)


if __name__ == "__main__":
    unittest.main()
