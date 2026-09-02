import unittest

from kex_proven_core import Mutation, PromotionGate, build_minframe


class ProvenCoreTests(unittest.TestCase):
    def test_minframe_separates_surfaces(self):
        registry, _, _ = build_minframe()
        self.assertEqual(registry.get("runtime://kex/core").parent, "volume://keddeh/braink/root")
        self.assertNotEqual(registry.get("app://kex/computer").surface, registry.get("runtime://kex/core").surface)

    def test_mutation_is_admitted_through_kex(self):
        _, ledger, admission = build_minframe()
        identity = "app://kex/active-state"
        base = admission.seed(identity, {"v": 1})
        receipt = admission.admit(Mutation("braink://local/orchestrator", identity, "SET_STATE", identity, {"v": 2}, base))
        self.assertTrue(receipt.event.startswith("KEX_ADMIT:"))
        self.assertTrue(ledger.verify())

    def test_stale_delta_is_rejected(self):
        _, _, admission = build_minframe()
        identity = "app://kex/active-state"
        base = admission.seed(identity, {"v": 1})
        admission.admit(Mutation("worker://one", identity, "SET_STATE", identity, {"v": 2}, base))
        with self.assertRaises(RuntimeError):
            admission.admit(Mutation("worker://two", identity, "SET_STATE", identity, {"v": 3}, base))

    def test_identity_rename_is_rejected(self):
        _, _, admission = build_minframe()
        identity = "app://kex/active-state"
        base = admission.seed(identity, {"v": 1})
        with self.assertRaises(PermissionError):
            admission.admit(Mutation("worker://one", identity, "RENAME_IDENTITY", identity, {"to": "app://other"}, base))

    def test_public_promotion_fails_closed(self):
        _, ledger, _ = build_minframe()
        receipt = PromotionGate(ledger).evaluate("volume://keddeh/braink/root", {"DNS": True})
        self.assertEqual(receipt.state.value, "VERIFIED_LOCAL")
        self.assertTrue(ledger.verify())

    def test_public_promotion_requires_all_receipts(self):
        _, ledger, _ = build_minframe()
        all_proofs = {name: True for name in PromotionGate.REQUIRED_PUBLIC}
        receipt = PromotionGate(ledger).evaluate("volume://keddeh/braink/root", all_proofs)
        self.assertEqual(receipt.state.value, "PUBLIC_READBACK")


if __name__ == "__main__":
    unittest.main()
