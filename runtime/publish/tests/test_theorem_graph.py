import unittest

from braink_runtime.theorem_graph import (
    ClaimState,
    EvidenceRef,
    GraphRelation,
    GraphViolation,
    OperatorSet,
    PropagationOutcome,
    RelationType,
    RoutingContract,
    SectorTransform,
    TheoremObject,
    TheoremRegistry,
)

SECTORS=("cosmology","linguistics","governance","runtime","proof","observer","motif")


def theorem(theorem_id, *, inp=("state",), out=("admissibility",), state=ClaimState.DECLARED, sectors=SECTORS, depth=2):
    return TheoremObject(
        theorem_id=theorem_id,
        canonical_name=theorem_id,
        version="1.0.0",
        canonical_definition="Zero is not admitted as a live operational state.",
        invariant="Zero is not an admissible operational state.",
        domain="KEX",
        input_types=inp,
        output_types=out,
        admissibility_constraints=("ZERO_NOT_LIVE_STATE",),
        operators=OperatorSet(local=("reject_zero",)),
        routing=RoutingContract(tuple(sectors), propagation_depth=depth),
        claim_state=state,
    )


class TheoremGraphTests(unittest.TestCase):
    def test_type_mismatch_relation_rejected(self):
        r=TheoremRegistry(); r.register(theorem("A",out=("admissibility",))); r.register(theorem("B",inp=("geometry",)))
        with self.assertRaisesRegex(GraphViolation,"RELATION_TYPE_MISMATCH"):
            r.connect(GraphRelation("A","B",RelationType.DEPENDS_ON))

    def test_verified_invariant_routes_to_seven_sectors(self):
        r=TheoremRegistry(); inv=theorem("INV-ZL-001",state=ClaimState.VERIFIED); r.register(inv)
        for sector in SECTORS:
            r.register_transform(SectorTransform(f"tx:{sector}",sector,("admissibility",),(f"{sector}-application",),lambda t,s=sector:{"application":f"application({t.theorem_id},{s})"}))
        apps=r.route("INV-ZL-001")
        self.assertEqual(len(apps),7)
        self.assertEqual({x.sector for x in apps},set(SECTORS))
        self.assertTrue(all(x.source_root==inv.object_root for x in apps))

    def test_unlisted_sector_does_not_receive_route(self):
        r=TheoremRegistry(); inv=theorem("INV-ZL-001",sectors=("runtime",)); r.register(inv)
        r.register_transform(SectorTransform("tx:runtime","runtime",("admissibility",),("runtime-application",),lambda t:{"ok":True}))
        r.register_transform(SectorTransform("tx:cosmo","cosmology",("admissibility",),("cosmo-application",),lambda t:{"ok":True}))
        apps=r.route("INV-ZL-001")
        self.assertEqual([x.sector for x in apps],["runtime"])

    def test_verified_upstream_strengthens_typed_dependent_only(self):
        r=TheoremRegistry(); a=theorem("A",state=ClaimState.VERIFIED); b=theorem("B",inp=("admissibility",),out=("runtime-state",)); r.register(a); r.register(b)
        r.connect(GraphRelation("A","B",RelationType.DEPENDS_ON))
        events=r.propagate("A")
        self.assertEqual(events[0].outcome,PropagationOutcome.STRENGTHENED)
        self.assertEqual(r.objects["B"].claim_state,ClaimState.OBSERVED)

    def test_falsification_propagates_review_requirement(self):
        r=TheoremRegistry(); a=theorem("A",state=ClaimState.VERIFIED); b=theorem("B",inp=("admissibility",),out=("runtime-state",),state=ClaimState.OBSERVED); c=theorem("C",inp=("runtime-state",),out=("proof-state",),state=ClaimState.VERIFIED)
        for x in (a,b,c): r.register(x)
        r.connect(GraphRelation("A","B",RelationType.DEPENDS_ON)); r.connect(GraphRelation("B","C",RelationType.DEPENDS_ON))
        ev=EvidenceRef("ce:1","counterexample",ClaimState.FALSIFIED,"evidence://counterexample/1")
        events=r.set_claim_state("A",ClaimState.FALSIFIED,evidence=ev)
        self.assertEqual(r.objects["B"].claim_state,ClaimState.REVIEW_REQUIRED)
        self.assertEqual(r.objects["C"].claim_state,ClaimState.REVIEW_REQUIRED)
        self.assertIn(PropagationOutcome.INVALIDATED,{e.outcome for e in events})

    def test_contested_contradiction_does_not_over_promote(self):
        r=TheoremRegistry(); a=theorem("A",state=ClaimState.OBSERVED); b=theorem("B",inp=("admissibility",),state=ClaimState.SPECIFIED); r.register(a); r.register(b)
        r.connect(GraphRelation("A","B",RelationType.CONTRADICTS))
        events=r.propagate("A")
        self.assertEqual(events[0].outcome,PropagationOutcome.COMPATIBLE)
        self.assertEqual(r.objects["B"].claim_state,ClaimState.SPECIFIED)

    def test_verified_contradiction_marks_target_contested(self):
        r=TheoremRegistry(); a=theorem("A",state=ClaimState.VERIFIED); b=theorem("B",inp=("admissibility",),state=ClaimState.VERIFIED); r.register(a); r.register(b)
        r.connect(GraphRelation("A","B",RelationType.CONTRADICTS))
        events=r.propagate("A")
        self.assertEqual(events[0].outcome,PropagationOutcome.CONTRADICTED)
        self.assertEqual(r.objects["B"].claim_state,ClaimState.CONTESTED)

    def test_compression_removes_only_exact_restatement_without_unique_evidence(self):
        r=TheoremRegistry(); r.register(theorem("INV-ZL-001"))
        result=r.factor_restatements("INV-ZL-001",[
            {"fragment_id":"f1","text":"Zero is not an admissible operational state."},
            {"fragment_id":"f2","text":"Zero is not an admissible operational state.","unique_evidence":["proof://2"]},
            {"fragment_id":"f3","text":"Runtime rejects zero addresses.","context_delta":"runtime-addressing"},
        ])
        self.assertEqual(result["eliminated"],("f1",))
        self.assertEqual(len(result["retained"]),2)

    def test_projection_is_computed_from_current_claim_state(self):
        r=TheoremRegistry(); inv=theorem("INV-ZL-001",state=ClaimState.VERIFIED,sectors=("runtime",)); r.register(inv)
        r.register_transform(SectorTransform("tx:runtime","runtime",("admissibility",),("runtime-application",),lambda t:{"constraint":"reject-zero"}))
        r.route("INV-ZL-001"); p1=r.render_sector("runtime")
        r.objects["INV-ZL-001"].claim_state=ClaimState.FALSIFIED; p2=r.render_sector("runtime")
        self.assertNotEqual(p1.projection_root,p2.projection_root)
        self.assertEqual(p2.proof_states["INV-ZL-001"],"FALSIFIED")

    def test_recursive_density_rises_when_reuse_rises_and_narrative_falls(self):
        r=TheoremRegistry(); inv=theorem("INV-ZL-001",state=ClaimState.VERIFIED,sectors=("runtime","proof")); r.register(inv)
        before=r.recursive_density(10)
        for sector in ("runtime","proof"):
            r.register_transform(SectorTransform(f"tx:{sector}",sector,("admissibility",),(f"{sector}-application",),lambda t,s=sector:{"application":s}))
        r.route("INV-ZL-001")
        inv.tests.append(EvidenceRef("test:1","test",ClaimState.VERIFIED,"test://1"))
        after=r.recursive_density(2)
        self.assertGreater(after,before)

    def test_operator_inheritance_is_dependency_scoped_and_honours_prohibition(self):
        r=TheoremRegistry()
        parent=theorem("P",state=ClaimState.VERIFIED)
        child=theorem("C",inp=("admissibility",),out=("runtime-state",))
        parent.operators=OperatorSet(local=("reject_zero","propagate_proof"))
        child.operators=OperatorSet(local=("render_state",),prohibited=("propagate_proof",))
        r.register(parent); r.register(child)
        r.connect(GraphRelation("P","C",RelationType.DEPENDS_ON))
        self.assertEqual(r.resolved_operators("C"),("reject_zero","render_state"))

    def test_marginal_value_counts_reuse_and_duplicate_cost(self):
        r=TheoremRegistry(); inv=theorem("I",state=ClaimState.VERIFIED,sectors=("runtime",)); dep=theorem("D",inp=("admissibility",),out=("runtime-state",))
        r.register(inv); r.register(dep); r.connect(GraphRelation("I","D",RelationType.DEPENDS_ON))
        r.register_transform(SectorTransform("tx:runtime","runtime",("admissibility",),("runtime-application",),lambda t:{"ok":True}))
        r.route("I")
        self.assertGreater(r.marginal_value("I",duplicate_cost=0), r.marginal_value("I",duplicate_cost=2))


if __name__ == "__main__":
    unittest.main()
