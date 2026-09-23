import unittest

from runtime.illlm_fabric import (
    Continuation, EvidenceClass, EvidenceRecord, ObserverFrame,
    Relation, SemanticConflict, SemanticObject, build_btc_semantic_seed,
)


class ILLLMFabricTests(unittest.TestCase):
    def setUp(self):
        self.f = build_btc_semantic_seed()

    def test_kex_round_trip_is_identity_bounded(self):
        binding = self.f.encode("il-llm://btc/core/bitcoin-core")
        projection = self.f.decode(binding.kex_id)
        self.assertEqual(projection["semantic"]["identity"], "il-llm://btc/core/bitcoin-core")
        self.assertEqual(projection["relations"], [])

    def test_aliases_share_one_semantic_and_kex_identity(self):
        first = self.f.encode("Bitcoin Core")
        second = self.f.encode("il-llm://btc/core/bitcoin-core")
        self.assertEqual(first.kex_id, second.kex_id)

    def test_kex_binding_rejects_semantic_mutation(self):
        self.f.encode("Bitcoin Core")
        with self.assertRaises(SemanticConflict):
            self.f.register(SemanticObject(
                "il-llm://btc/core/bitcoin-core", "different-kind", ("Bitcoin Core",)
            ))

    def test_depth_one_does_not_explode_recursive_graph(self):
        binding = self.f.encode("Bitcoin Core")
        projection = self.f.decode(binding.kex_id, depth=1)
        self.assertNotIn("expanded", projection)

    def test_explicit_depth_traverses_relations(self):
        binding = self.f.encode("Bitcoin Core")
        projection = self.f.decode(binding.kex_id, depth=2)
        targets = {r["target"] for r in projection["relations"]}
        self.assertIn("il-llm://btc/work/getblocktemplate", targets)

    def test_observer_plurality_does_not_mutate_source(self):
        source = self.f.resolve("Core GBT")
        before = source.canonical_payload()
        self.f.observe(ObserverFrame(
            source.identity, "il-llm://authority", "il-llm://observer/verifier",
            {"interpretation": "requires Bitcoin Core authority"}, epoch="418"
        ))
        self.f.observe(ObserverFrame(
            source.identity, "il-llm://planning", "il-llm://observer/verifier",
            {"interpretation": "unblocks candidate construction"}, epoch="418"
        ))
        self.assertEqual(before, self.f.resolve("Core GBT").canonical_payload())
        self.assertEqual(len(self.f.frames), 2)

    def test_plural_continuations_coexist(self):
        a = Continuation("continuation://btc", "il-llm://btc", "il-llm://observer/verifier")
        b = Continuation("continuation://proof", "il-llm://proof", "il-llm://observer/verifier")
        self.f.put_continuation(a)
        self.f.put_continuation(b)
        self.assertEqual(set(self.f.continuations), {"continuation://btc", "continuation://proof"})
        advanced = a.advance("il-llm://btc/work/getblocktemplate", via="ACQUIRE")
        self.f.put_continuation(advanced)
        self.assertEqual(self.f.continuations["continuation://btc"].logical_time, 1)
        self.assertEqual(self.f.continuations["continuation://proof"].logical_time, 0)

    def test_authority_is_graph_resident_not_flat_dictionary(self):
        rels = self.f.traverse("Core GBT", predicate="REQUIRES_AUTHORITY")
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].target, "il-llm://authority/class/bitcoin-core")

    def test_synthetic_evidence_cannot_satisfy_default_proof(self):
        event = SemanticObject("btc://event/GBT/418", "event", ("GBT 418",))
        self.f.register(event)
        rec = EvidenceRecord(
            "receipt://synthetic/418", event.identity, "projection://test",
            EvidenceClass.SYNTHETIC, "00" * 32, epoch="418", session="core-a"
        )
        self.f.append_evidence(rec)
        self.assertFalse(self.f.verify_evidence_scope(
            rec.identity, subject=event.identity, epoch="418", session="core-a"
        ))

    def test_stale_epoch_evidence_fails_scope(self):
        event = SemanticObject("btc://event/GBT/418", "event", ("GBT 418",))
        self.f.register(event)
        rec = EvidenceRecord(
            "receipt://rpc/418", event.identity, "btc://bitcoin-core/mainnet",
            EvidenceClass.OBSERVED, "11" * 32, epoch="418", session="core-a"
        )
        self.f.append_evidence(rec)
        self.assertTrue(self.f.verify_evidence_scope(rec.identity, subject=event.identity, epoch="418", session="core-a"))
        self.assertFalse(self.f.verify_evidence_scope(rec.identity, subject=event.identity, epoch="419", session="core-a"))

    def test_new_gbt_can_supersede_without_deleting_history(self):
        old = SemanticObject("btc://event/GBT/418", "event", ("GBT 418",))
        new = SemanticObject("btc://event/GBT/419", "event", ("GBT 419",))
        self.f.register(old); self.f.register(new)
        self.f.relate(Relation(new.identity, "il-llm://predicate/supersedes", old.identity, epoch="419"))
        self.assertIn(old.identity, self.f.objects)
        self.assertIn(new.identity, self.f.objects)
        rels = self.f.traverse(new.identity, predicate="SUPERSEDES")
        self.assertEqual(rels[0].target, old.identity)


if __name__ == "__main__":
    unittest.main()
