#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

REQUIRED_RECORD_FIELDS = {
    "canonical_id",
    "canonical_name",
    "origin_authority",
    "origin_type",
    "source_lineage",
    "semantic_roots",
    "design_problem",
    "architectural_role",
    "native_context",
    "valid_cross_contexts",
    "inherited_capabilities",
    "specialised_capabilities",
    "bilateral_interfaces",
    "prohibited_conflations",
    "evidence",
    "promotion_state",
    "version",
}

USER_ORIGIN_TYPES = {
    "USER_DESIGNED",
    "USER_NAMED_FROM_PRIOR_DESIGN",
    "DERIVED_FROM_USER_ARCHITECTURE",
}


def load_json(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate_naming_attribution() -> list[str]:
    errors: list[str] = []
    conventions = load_json("naming_conventions.json")
    schema = load_json("naming_attribution.schema.json")
    registry = load_json("keddeh_name_lineage_registry.json")
    standard = (ROOT / "NAMING_ATTRIBUTION_STANDARD.md").read_text(encoding="utf-8")

    semantic = conventions.get("semantic_attribution", {})
    if conventions.get("version") != "2.0.0":
        errors.append("conventions:unexpected_version")
    if semantic.get("standard") != "NAMING_ATTRIBUTION_STANDARD.md":
        errors.append("conventions:missing_standard_binding")
    if semantic.get("schema") != "naming_attribution.schema.json":
        errors.append("conventions:missing_schema_binding")
    if "assistant formalisation does not transfer authorship" not in semantic.get("origin_authority_rule", ""):
        errors.append("conventions:user_authority_not_preserved")

    schema_required = set(schema.get("required", []))
    if not REQUIRED_RECORD_FIELDS.issubset(schema_required):
        errors.append("schema:required_fields_incomplete")

    records = registry.get("records", [])
    if not records:
        errors.append("registry:no_records")
        return errors

    expected_names = {
        "Keddeh PlayWrite",
        "Keddeh Coms",
        "Spin^",
        "LawPath",
        "FormPath",
        "ClaimPath",
    }
    actual_names = {record.get("canonical_name") for record in records}
    for name in sorted(expected_names - actual_names):
        errors.append(f"registry:missing_name:{name}")

    identities: set[str] = set()
    for index, record in enumerate(records):
        missing = REQUIRED_RECORD_FIELDS - set(record)
        for field in sorted(missing):
            errors.append(f"registry:{index}:missing:{field}")

        identity = record.get("canonical_id")
        if identity in identities:
            errors.append(f"registry:duplicate_identity:{identity}")
        if identity:
            identities.add(identity)

        if record.get("origin_type") in USER_ORIGIN_TYPES and record.get("origin_authority") != "A. Keddeh":
            errors.append(f"registry:{identity}:user_origin_authority_lost")
        if not record.get("source_lineage"):
            errors.append(f"registry:{identity}:empty_lineage")
        if not record.get("semantic_roots"):
            errors.append(f"registry:{identity}:empty_semantic_roots")
        if not record.get("inherited_capabilities"):
            errors.append(f"registry:{identity}:inherited_capabilities_compressed")
        if not record.get("specialised_capabilities"):
            errors.append(f"registry:{identity}:specialised_capabilities_missing")
        if not record.get("prohibited_conflations"):
            errors.append(f"registry:{identity}:conflation_boundary_missing")
        if not any(
            evidence.get("evidence_class") == "DIRECT_USER_DESIGN_STATEMENT"
            for evidence in record.get("evidence", [])
        ):
            errors.append(f"registry:{identity}:direct_user_design_evidence_missing")

    for phrase in (
        "KEDDEH names are engineering coordinates, not decorative labels",
        "assistant formalisation as original authorship",
        "Contextual cross-application",
        "Attribution is not capability compression",
    ):
        if phrase not in standard:
            errors.append(f"standard:missing:{phrase}")

    if registry.get("global_stop") is not False:
        errors.append("registry:global_stop_must_be_false")

    return errors


def main() -> int:
    errors = validate_naming_attribution()
    print(
        json.dumps(
            {
                "standard": "standard://keddeh/naming-attribution",
                "registry": "registry://keddeh/name-lineage",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
