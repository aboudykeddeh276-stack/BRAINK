"""R91 source-bound tests for the R5 cross-work relation graph.

Architect: A. Keddeh
Canonical architecture: KS-BRAINK-IL-LLM
These tests validate relation readback, not target execution.
"""
import hashlib, json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"estate"
R5=DOCS/"source-copies"/"r5"
D=json.loads((DOCS/"R91_RELATION_TRAVERSAL.json").read_text())
B=json.loads((R5/"BRAINK_R5_SYSTEM_MANIFEST.json").read_text())
P=DOCS/"R91_RELATION_GRAPH_PROJECTION.json"
C=json.loads(P.read_text())

def test_authority_and_canonical_name():
    assert D["architect"]=="A. Keddeh" and D["canonicalArchitecture"]=="KS-BRAINK-IL-LLM"

def test_cross_work_source_hash_and_parent_binding():
    assert C["sourceBytes"]==39430
    assert C["sourceSha256"]==D["sources"]["crossWorkManifest"]["sha256"]
    assert C["parent_system_orchestrator"]["identity"]==B["identity"]
    assert C["parent_system_orchestrator"]["sha256"]==D["parentBinding"]["parentSha256"]
    assert C["parent_system_orchestrator"]["manifest_sha256"]==D["parentBinding"]["standaloneManifestSha256"]

def test_23_base_edges_are_exact_prefix_and_nine_are_additive():
    assert len(B["relations"])==23 and len(C["relations"])==32
    assert C["relations"][:23]==B["relations"] and len(C["relations"][23:])==9

def test_32_unique_edges_and_endpoint_classification():
    E=C["relations"]
    assert len({(x["source"],x["relation"],x["target"]) for x in E})==32
    assert D["relationClosure"]["allEndpointsClassified"] is True
    assert D["relationClosure"]["edgeTypes"]==dict(Counter(x["relation"] for x in E))
    assert sum(D["relationClosure"]["endpointClassCounts"].values())==24

def test_route_and_return_edges_use_registered_relation_sector():
    b=C["cross_work_bindings"][0]; e=C["relations"][23:]
    r=[x for x in e if x["relation"]=="ROUTES_WORK_TO"]
    q=[x for x in e if x["relation"]=="RETURNS_WORK_TO"]
    sector=C["relation_sectors"][0]["identity"]
    assert b["state"]=="ADMITTED_RELATION_ROUTE_NOT_TARGET_EXECUTION"
    assert len(r)==len(q)==4 and all(x["via"]==sector for x in r+q)
    assert {x["target"] for x in r}==set(b["targets"])
    assert {x["source"] for x in q}==set(b["targets"])

def test_r3_and_research_fabric_source_hashes_are_pinned():
    s=D["sources"]
    assert s["r3Source"]["sha256"]=="20dfd28194dd928aa55e181ac2a04f6ffe807175641da16930a4387f96357956"
    assert s["researchFabric"]["sha256"]=="9aaf61466c123acc0554ce0a1514b40bd57b824b9bfeea0ac2b3313e150d294b"

def test_sector_states_do_not_promote_s29():
    s={x["sector_id"]:x for x in D["researchSectors"]}
    assert set(s)=={"S26","S27","S28","S29"}
    assert all(s[x]["state"]=="RESEARCH_SECTOR_INSTANTIATED" for x in ("S26","S27","S28"))
    assert s["S29"]["state"]=="UNIVERSALITY_OPEN"

def test_title_mismatch_is_retained():
    t=D["surfaceMetadataReview"]
    assert t["manifestTitle"]=="KEDDEH v71 Research Sector Fabric S26-S29"
    assert t["actualHtmlTitle"]=="KEX Linux Computer v70" and t["titleMatch"] is False

def test_no_target_execution_or_consciousness_claim():
    b=D["claimBoundary"]
    assert b["relationAdmissionIsNotExecution"] is True
    assert b["formalUniversality"]=="OPEN" and b["quantumEquivalence"]=="NOT_PROVEN"
    assert b["subjectiveConsciousnessProven"] is False and b["externalHostAdmission"]=="NOT_ESTABLISHED"
