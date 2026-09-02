import json
from pathlib import Path
from enterprise.foundry_runtime import FoundaryRuntime

ROOT = Path(__file__).resolve().parents[2]
registry = json.loads((ROOT / "enterprise" / "FOUNDRY_REGISTRY_R21.json").read_text("utf-8"))
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

composition = rt.compose_undertaking("LEGAL_SERVICE", required)
assert set(composition["foundaries"]) == required
assert "domain mastery" in composition["process_domains"]
assert "self-coding" in composition["process_domains"]
assert "K-DRIVE semantics" in composition["process_domains"]
assert "customer files" in composition["process_domains"]
assert "SVG generation" in composition["process_domains"]
assert "AI server rooms" in composition["process_domains"]
assert len(composition["undertaking_root"]) == 64
print("R21_FOUNDRY_RUNTIME_PASS")
