from __future__ import annotations
import json
from braink_runtime.theorem_graph import *

SECTORS=("cosmology","linguistics","governance","runtime","proof","observer","motif")

def make(tid, inp, out, state, sectors=SECTORS, depth=3, local_ops=()):
    return TheoremObject(
        theorem_id=tid, canonical_name=tid, version="1.0.0",
        canonical_definition="Zero is not admitted as a live operational state.",
        invariant="Zero is not an admissible operational state.", domain="KEX",
        input_types=tuple(inp), output_types=tuple(out),
        admissibility_constraints=("ZERO_NOT_LIVE_STATE",),
        operators=OperatorSet(local=tuple(local_ops)),
        routing=RoutingContract(tuple(sectors), propagation_depth=depth),
        claim_state=state,
    )

r=TheoremRegistry()
inv=make("INV-ZL-001",("state",),("admissibility",),ClaimState.VERIFIED,local_ops=("reject_zero","propagate_proof"))
r.register(inv)
for sector in SECTORS:
    r.register_transform(SectorTransform(
        f"tx:{sector}:zl", sector, ("admissibility",), (f"{sector}-constraint",),
        lambda t, s=sector: {
            "projection": f"application({t.theorem_id},{s})",
            "stored_meaning": "canonical invariant + sector transform + unique evidence",
        }
    ))

# Typed downstream chain: invariant -> runtime constraint -> proof claim -> HCI/page state.
runtime=make("TH-RUNTIME-ZL",("admissibility",),("runtime-state",),ClaimState.SPECIFIED,sectors=("runtime",),local_ops=("render_runtime",))
proof=make("TH-PROOF-ZL",("runtime-state",),("proof-state",),ClaimState.SPECIFIED,sectors=("proof",),local_ops=("emit_receipt",))
page=make("TH-PAGE-ZL",("proof-state",),("projection-state",),ClaimState.SPECIFIED,sectors=("runtime","proof"),local_ops=("render_page",))
for obj in (runtime,proof,page): r.register(obj)
r.connect(GraphRelation("INV-ZL-001","TH-RUNTIME-ZL",RelationType.DEPENDS_ON))
r.connect(GraphRelation("TH-RUNTIME-ZL","TH-PROOF-ZL",RelationType.DEPENDS_ON))
r.connect(GraphRelation("TH-PROOF-ZL","TH-PAGE-ZL",RelationType.DEPENDS_ON))

apps=r.route("INV-ZL-001")
pre_runtime=r.render_sector("runtime")
pre_proof=r.render_sector("proof")
positive=r.propagate("INV-ZL-001")
ops=r.resolved_operators("TH-RUNTIME-ZL")
compression=r.factor_restatements("INV-ZL-001",[
    {"fragment_id":f"repeat:{s}","text":"Zero is not an admissible operational state."} for s in SECTORS
] + [
    {"fragment_id":"runtime:delta","text":"Runtime rejects zero addresses and live zero state.","context_delta":"runtime address/state enforcement","unique_evidence":["test://runtime-zero"]}
])
density_before=r.recursive_density(12)
density_after=r.recursive_density(1)
growth=r.marginal_value("INV-ZL-001",duplicate_cost=len(compression["eliminated"]))

# Inject falsification and demand symmetric negative propagation.
ce=EvidenceRef("counterexample:zl:1","counterexample",ClaimState.FALSIFIED,"evidence://counterexample/zl/1")
negative=r.set_claim_state("INV-ZL-001",ClaimState.FALSIFIED,evidence=ce)
# Re-route to refresh theorem-derived application state after source state changes.
r.route("INV-ZL-001")
post_runtime=r.render_sector("runtime")
post_proof=r.render_sector("proof")

summary={
    "schema":"braink.theorem-graph.campaign.v1",
    "registered_objects":len(r.objects),
    "relations":len(r.relations),
    "sector_applications":len(apps),
    "sectors":sorted(a.sector for a in apps),
    "positive_events":[{**asdict(e),"relation":e.relation.value,"outcome":e.outcome.value,"prior_state":e.prior_state.value,"next_state":e.next_state.value} for e in positive],
    "resolved_runtime_operators":ops,
    "compression":compression,
    "recursive_density_before":density_before,
    "recursive_density_after":density_after,
    "marginal_value_after_factoring":growth,
    "falsification_events":[{**asdict(e),"relation":e.relation.value,"outcome":e.outcome.value,"prior_state":e.prior_state.value,"next_state":e.next_state.value} for e in negative],
    "final_claim_states":{k:v.claim_state.value for k,v in sorted(r.objects.items())},
    "projection_roots":{
        "runtime_before":pre_runtime.projection_root,
        "runtime_after":post_runtime.projection_root,
        "proof_before":pre_proof.projection_root,
        "proof_after":post_proof.projection_root,
    },
    "projection_changed":{
        "runtime":pre_runtime.projection_root!=post_runtime.projection_root,
        "proof":pre_proof.projection_root!=post_proof.projection_root,
    },
    "campaign_pass": (
        len(apps)==7
        and set(a.sector for a in apps)==set(SECTORS)
        and compression["eliminated"]==tuple(f"repeat:{s}" for s in SECTORS)
        and r.objects["TH-RUNTIME-ZL"].claim_state==ClaimState.REVIEW_REQUIRED
        and r.objects["TH-PROOF-ZL"].claim_state==ClaimState.REVIEW_REQUIRED
        and r.objects["TH-PAGE-ZL"].claim_state==ClaimState.REVIEW_REQUIRED
        and pre_runtime.projection_root!=post_runtime.projection_root
        and pre_proof.projection_root!=post_proof.projection_root
    )
}
print(json.dumps(summary,indent=2))
raise SystemExit(0 if summary["campaign_pass"] else 1)
