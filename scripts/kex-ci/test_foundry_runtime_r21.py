import json
import tempfile
from pathlib import Path
from enterprise.foundry_runtime import FoundaryRuntime
from enterprise.foundry_operations_r22 import FoundaryOperationsRuntime

ROOT = Path(__file__).resolve().parents[2]
registry = json.loads((ROOT / "enterprise" / "FOUNDRY_REGISTRY_R21.json").read_text("utf-8"))
topology = json.loads((ROOT / "enterprise" / "FOUNDARY_DEPLOYMENT_TOPOLOGY_R21.json").read_text("utf-8"))
publish_receipt = json.loads((ROOT / "deployments" / "R21_PUBLISHING_ACTUATOR_BINDING_R1.json").read_text("utf-8"))
rt = FoundaryRuntime(registry)

required = {
    "FRONTAGES_SERVICES_GROWING_MESH_WEBSITES_DOMAIN_MASTERY_FOUNDARY",
    "PROCESS_MASTERY_FOUNDARY",
    "RESEARCH_MASTERY_FOUNDARY",
    "PUBLISHING_MASTERY_FOUNDARY",
    "AGENTICS_FOUNDARY",
    "HR_AND_ALL_TEAM_SERVICES_FOUNDARY",
    "BUSINESS_AND_ENTERPRISE_STRUCTURE_FOUNDARY",
    "SERVER_FOUNDARY",
    "REAL_ACTUAL_USEABLE_SOFTWARE_FOUNDARY",
    "HCI_FOUNDARY",
    "LANDING_PAGE_FOUNDARY",
    "SVG_FOUNDARY",
    "WORKSPACE_FOUNDARY",
    "FILE_SYSTEM_FOUNDARY",
    "CUSTOMER_FILE_BASE_SOFTWARE_FOUNDARY",
}
assert required.issubset(set(rt.foundaries))

for foundary_id in required:
    addr = rt.address(foundary_id)
    assert addr.process_count >= 5
    assert addr.server_set_count >= 1
    assert addr.team_count >= 1
    assert addr.data_class_count >= 1
    assert addr.repository_count >= 1
    assert addr.virtual_root_count >= 1
    packet = rt.materialize("LEGAL_SERVICE", foundary_id)
    source = registry["foundaries"][foundary_id]
    assert set(packet.process_domains) == set(source["process_domains"])
    assert set(packet.server_sets) == set(source["server_sets"])
    assert set(packet.agent_teams) == set(source["agent_teams"])
    assert set(packet.data_classes) == set(source["data_classes"])
    assert set(packet.repositories) == set(source["repositories"])
    assert set(packet.virtual_roots) == set(source["virtual_roots"])

composition = rt.compose_undertaking("LEGAL_SERVICE", required)
assert set(composition["foundaries"]) == required
assert "domain mastery" in composition["process_domains"]
assert "self-coding" in composition["process_domains"]
assert "K-DRIVE semantics" in composition["process_domains"]
assert "customer files" in composition["process_domains"]
assert "SVG generation" in composition["process_domains"]
assert "AI server rooms" in composition["process_domains"]
assert len(composition["undertaking_root"]) == 64

# R21 publication reuse invariant: reuse resident R22 staging and the existing
# CasePath actuator rather than inventing parallel publishing mechanics.
pub = topology["resident_foundary_process_bindings"]["PUBLISHING_MASTERY_FOUNDARY"]
assert pub["receipt"] == "deployments/R21_PUBLISHING_ACTUATOR_BINDING_R1.json"
assert pub["publication_stage"] == "enterprise/foundry_operations_r22.py::PublishingMasteryFoundary.stage_release"
assert pub["mechanic"] == "mechanic://keddeh/admin/production-actuator"
assert "publication stage" in pub["bound_mechanics"]
assert "release actuator" in pub["bound_mechanics"]
assert "production origin write authority" in pub["not_promoted"]
assert publish_receipt["classification"] == "RESIDENT_STAGE_APPROVAL_AND_ACTUATOR_REUSE_BOUND_ORIGIN_AUTHORITY_PENDING"
assert publish_receipt["mechanic"] == pub["mechanic"]
assert publish_receipt["foundary_id"] == "PUBLISHING_MASTERY_FOUNDARY"
assert publish_receipt["foundary_mechanics_reconciled"]["publication_queue_or_stage"] == "RESIDENT_SOURCE_BOUND"
assert registry["foundaries"]["PUBLISHING_MASTERY_FOUNDARY"]["state"] == "PARTIALLY_BOUND"

# Deterministic source invariant for the newly resident R22 staging seam.
with tempfile.TemporaryDirectory() as td:
    state_path = Path(td) / "foundary-state.json"
    ops = FoundaryOperationsRuntime(state_path)
    ops.business.create_undertaking("LEGAL_SERVICE", "legal service", ["CASEPATH_SERVICE_GENOME_R1"], ["LEGAL"], ["SA"])
    ops.frontages.register_frontage("frontage://casepath", "LEGAL_SERVICE", "casepath.com.au", {"/": "landing://casepath"}, ["mesh://alpha"])
    landing_receipt = ops.landing.manufacture(
        "landing://casepath",
        "LEGAL_SERVICE",
        "frontage://casepath",
        "Legal service proposition",
        [{"kind": "hero", "content": "CasePath"}],
        ["BEGIN_INTAKE"],
    )
    assert landing_receipt.status == "COMMITTED"
    release_receipt = ops.publishing.stage_release(
        "release://casepath/r21-test",
        "LEGAL_SERVICE",
        ["landing://casepath"],
        "frontage://casepath",
        [{"authority": "GENERAL-GOVERNANCE-/braink_hr", "decision": "APPROVE"}],
    )
    assert release_receipt.status == "COMMITTED"
    staged = ops.store.state["publications"]["release://casepath/r21-test"]
    assert staged["state"] == "STAGED_INTERNAL"
    assert staged["approvals"][0]["authority"] == "GENERAL-GOVERNANCE-/braink_hr"
    assert len(staged["release_root"]) == 64
    predecessor_root = ops.store.state["state_root"]
    restored = FoundaryOperationsRuntime(state_path)
    assert restored.store.state["state_root"] == predecessor_root
    assert restored.store.state["publications"]["release://casepath/r21-test"]["release_root"] == staged["release_root"]

print("R21_FOUNDRY_RUNTIME_PASS")
