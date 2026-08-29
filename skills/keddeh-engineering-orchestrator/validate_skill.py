#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def load_json(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    manifest = load_json("skill_manifest.json")
    routing = load_json("tool_routing.json")
    schema = load_json("evidence_contract.schema.json")
    topology_schema = load_json("software_topology.schema.json")
    naming = load_json("naming_conventions.json")
    lifecycle = load_json("iteration_lifecycle.json")
    language_matrix = load_json("LANGUAGE_TARGET_MATRIX.json")
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    topology_text = (ROOT / "SOFTWARE_TOPOLOGY_STANDARD.md").read_text(encoding="utf-8")
    kir_text = (ROOT / "KEDDEH_INTERMEDIATE_REPRESENTATION.md").read_text(encoding="utf-8")
    bilateral_text = (ROOT / "IL_LLM_BILATERAL_TRANSLATION_CONTRACT.md").read_text(encoding="utf-8")

    if manifest.get("skill_id") != "skill://keddeh/engineering-orchestrator":
        errors.append("manifest:invalid_skill_id")
    if manifest.get("version") != "1.2.0":
        errors.append("manifest:unexpected_version")
    if manifest.get("path_order") != ["path_a", "path_b", "path_c"]:
        errors.append("manifest:invalid_path_order")
    if manifest.get("allow_partial_path_blending") is not False:
        errors.append("manifest:partial_path_blending_not_disabled")
    if manifest.get("global_stop") is not False:
        errors.append("manifest:global_stop_must_be_false")
    if "Lovable" not in manifest.get("excluded_tools", []):
        errors.append("manifest:lovable_not_excluded")

    translation = manifest.get("translation_architecture", {})
    if translation.get("translation_layer") != "IL-LLM":
        errors.append("manifest:invalid_translation_layer")
    if translation.get("canonical_ir") != "ir://keddeh/system-synthesis":
        errors.append("manifest:invalid_canonical_ir")
    if translation.get("bilateral_contract") != "contract://keddeh/il-llm-bilateral-translation":
        errors.append("manifest:invalid_bilateral_contract")
    expected_equivalence = {
        "SEMANTIC_EQUIVALENT",
        "SEMANTIC_EQUIVALENT_WITH_DECLARED_ADAPTERS",
        "PARTIAL_EQUIVALENCE",
        "TRANSLATION_GAP",
        "INVALID_TARGET",
    }
    if set(translation.get("equivalence_states", [])) != expected_equivalence:
        errors.append("manifest:invalid_equivalence_states")

    expected_levels = [
        "L0_ECOSYSTEM", "L1_SYSTEM", "L2_DOMAIN", "L3_RUNTIME_CONTAINER",
        "L4_COMPONENT", "L5_CODE_UNIT", "L6_EXECUTION_TRANSITION", "L7_DEPLOYMENT_PROJECTION",
    ]
    if manifest.get("topology_levels") != expected_levels:
        errors.append("manifest:invalid_topology_levels")

    expected_views = {
        "CONTEXT_VIEW", "BUILDING_BLOCK_VIEW", "RUNTIME_VIEW", "DEPLOYMENT_VIEW",
        "DATA_LINEAGE_VIEW", "FAILURE_AND_RECOVERY_VIEW", "SECURITY_AND_TRUST_VIEW",
        "EVIDENCE_AND_PROMOTION_VIEW",
    }
    if set(manifest.get("required_architecture_views", [])) != expected_views:
        errors.append("manifest:invalid_architecture_views")

    prohibited = set(routing.get("prohibited", []))
    if "Lovable" not in prohibited:
        errors.append("routing:lovable_not_prohibited")
    if routing.get("selection_rule") is None:
        errors.append("routing:missing_selection_rule")

    domains = routing.get("domains", {})
    required_domains = {
        "repository_engineering", "source_and_lineage", "analysis_and_execution",
        "standards_research", "interface_and_hci", "workbook_control_plane",
        "formal_artifacts", "engineering_coordination", "openai_runtime",
        "recurring_governance",
    }
    for domain in sorted(required_domains - set(domains)):
        errors.append(f"routing:missing_domain:{domain}")
    for domain, contract in domains.items():
        for path in ("path_a", "path_b", "path_c"):
            if not contract.get(path):
                errors.append(f"routing:{domain}:missing:{path}")
        if not contract.get("required_outputs"):
            errors.append(f"routing:{domain}:missing_required_outputs")

    required_receipt_fields = set(schema.get("required", []))
    expected_receipt_fields = {
        "work_unit", "engineering_domain", "source_identities", "tools_invoked",
        "selected_path", "outputs", "tests", "artifact_state", "promotion_state",
        "impact_radius", "unaffected_domains", "remaining_gates", "global_stop",
    }
    if not expected_receipt_fields.issubset(required_receipt_fields):
        errors.append("schema:missing_required_receipt_fields")

    topology_required = set(topology_schema.get("required", []))
    for field in ("topology_id", "system_id", "nodes", "edges", "views", "iteration_id", "global_stop"):
        if field not in topology_required:
            errors.append(f"topology_schema:missing_required:{field}")
    if topology_schema.get("properties", {}).get("global_stop", {}).get("const") is not False:
        errors.append("topology_schema:global_stop_must_be_false")

    allowed_kinds = set(naming.get("allowed_identity_kinds", []))
    for kind in ("system", "domain", "service", "component", "interface", "workflow", "topology", "iteration"):
        if kind not in allowed_kinds:
            errors.append(f"naming:missing_identity_kind:{kind}")
    if naming.get("segment_case") != "lower-kebab-case":
        errors.append("naming:segment_case_invalid")
    if not re.fullmatch(r"MAJOR\.MINOR\.PATCH", naming.get("semantic_version_pattern", "")):
        errors.append("naming:semantic_version_pattern_invalid")

    states = [item.get("id") for item in lifecycle.get("iteration_states", [])]
    expected_states = [
        "I0_OBSERVE", "I1_DEFINE", "I2_DESIGN", "I3_IMPLEMENT", "I4_STATIC_VALIDATE",
        "I5_EXECUTE", "I6_INTEGRATE", "I7_PROMOTE", "I8_PRESERVE", "I9_REVIEW",
    ]
    if states != expected_states:
        errors.append("iteration:invalid_state_order")
    for item in lifecycle.get("iteration_states", []):
        if not item.get("required_outputs"):
            errors.append(f"iteration:{item.get('id')}:missing_required_outputs")
    if lifecycle.get("global_stop") is not False:
        errors.append("iteration:global_stop_must_be_false")

    if language_matrix.get("matrix_id") != "matrix://keddeh/language-target-capabilities":
        errors.append("language_matrix:invalid_id")
    required_families = {
        "freestanding_systems", "hosted_services", "hardware_description",
        "interface_and_configuration", "workbook_and_visual",
    }
    families = language_matrix.get("language_families", {})
    for family in sorted(required_families - set(families)):
        errors.append(f"language_matrix:missing_family:{family}")
    for family, contract in families.items():
        if not contract.get("languages"):
            errors.append(f"language_matrix:{family}:missing_languages")
        if not contract.get("uses"):
            errors.append(f"language_matrix:{family}:missing_uses")
        if not contract.get("mandatory_contracts"):
            errors.append(f"language_matrix:{family}:missing_contracts")
    if language_matrix.get("global_stop") is not False:
        errors.append("language_matrix:global_stop_must_be_false")

    canonical_files = manifest.get("canonical_files", {})
    for key, filename in canonical_files.items():
        if not (ROOT / filename).exists():
            errors.append(f"manifest:missing_canonical_file:{key}:{filename}")

    for phrase in (
        "Artifact preservation gate", "Deterministic capability routing",
        "Lovable exclusion", "No global stop", "IL-LLM bilateral synthesis authority",
    ):
        if phrase not in skill_text:
            errors.append(f"skill:missing_section:{phrase}")

    for phrase in (
        "Canonical topology levels", "Dependency-direction law", "Naming grammar",
        "Iteration structure", "Architecture decision records", "Design-quality gates",
    ):
        if phrase not in topology_text:
            errors.append(f"topology_standard:missing_section:{phrase}")

    for phrase in (
        "Required KIR planes", "Lowering contracts", "Bilateral semantic equivalence",
        "Hardware/software abstraction rule", "BIOS and firmware profile", "Server profile",
    ):
        if phrase not in kir_text:
            errors.append(f"kir:missing_section:{phrase}")

    for phrase in (
        "Bilateral lifecycle", "Round-trip invariant", "Language neutrality",
        "Hardware abstraction", "Translation failure handling",
    ):
        if phrase not in bilateral_text:
            errors.append(f"bilateral:missing_section:{phrase}")

    return errors


def main() -> int:
    errors = validate()
    result = {
        "skill_id": "skill://keddeh/engineering-orchestrator",
        "skill_version": "1.2.0",
        "valid": not errors,
        "errors": errors,
        "topology_standard": "standard://keddeh/software-topology",
        "canonical_ir": "ir://keddeh/system-synthesis",
        "translation_contract": "contract://keddeh/il-llm-bilateral-translation",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
