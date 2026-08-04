#!/usr/bin/env python3
from __future__ import annotations

import json
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
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    if manifest.get("skill_id") != "skill://keddeh/engineering-orchestrator":
        errors.append("manifest:invalid_skill_id")
    if manifest.get("path_order") != ["path_a", "path_b", "path_c"]:
        errors.append("manifest:invalid_path_order")
    if manifest.get("allow_partial_path_blending") is not False:
        errors.append("manifest:partial_path_blending_not_disabled")
    if manifest.get("global_stop") is not False:
        errors.append("manifest:global_stop_must_be_false")
    if "Lovable" not in manifest.get("excluded_tools", []):
        errors.append("manifest:lovable_not_excluded")

    prohibited = set(routing.get("prohibited", []))
    if "Lovable" not in prohibited:
        errors.append("routing:lovable_not_prohibited")
    if routing.get("selection_rule") is None:
        errors.append("routing:missing_selection_rule")

    domains = routing.get("domains", {})
    required_domains = {
        "repository_engineering",
        "source_and_lineage",
        "analysis_and_execution",
        "standards_research",
        "interface_and_hci",
        "workbook_control_plane",
        "formal_artifacts",
        "engineering_coordination",
        "openai_runtime",
        "recurring_governance",
    }
    missing_domains = required_domains - set(domains)
    for domain in sorted(missing_domains):
        errors.append(f"routing:missing_domain:{domain}")
    for domain, contract in domains.items():
        for path in ("path_a", "path_b", "path_c"):
            if not contract.get(path):
                errors.append(f"routing:{domain}:missing:{path}")
        if not contract.get("required_outputs"):
            errors.append(f"routing:{domain}:missing_required_outputs")

    required_receipt_fields = set(schema.get("required", []))
    expected_receipt_fields = {
        "work_unit",
        "engineering_domain",
        "source_identities",
        "tools_invoked",
        "selected_path",
        "outputs",
        "tests",
        "artifact_state",
        "promotion_state",
        "impact_radius",
        "unaffected_domains",
        "remaining_gates",
        "global_stop",
    }
    if not expected_receipt_fields.issubset(required_receipt_fields):
        errors.append("schema:missing_required_receipt_fields")

    for phrase in (
        "Artifact preservation gate",
        "Deterministic capability routing",
        "Lovable exclusion",
        "No global stop",
    ):
        if phrase not in skill_text:
            errors.append(f"skill:missing_section:{phrase}")

    return errors


def main() -> int:
    errors = validate()
    result = {
        "skill_id": "skill://keddeh/engineering-orchestrator",
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
