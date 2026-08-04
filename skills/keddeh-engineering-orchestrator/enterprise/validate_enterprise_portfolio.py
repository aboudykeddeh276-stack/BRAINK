#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_json(filename):
    return json.loads((ROOT / filename).read_text(encoding="utf-8"))


def validate():
    errors = []
    portfolio = read_json("portfolio-registry.json")
    naming = read_json("naming-lineage-registry.json")
    contracts = read_json("bilateral-contracts.json")
    trajectory = read_json("enterprise-trajectory.json")

    expected = {
        "Keddeh PlayWrite", "Keddeh Coms", "Spin^", "KEO", "BRAINK", "KEX",
        "LawPath", "FormPath", "ClaimPath", "Legal/Regulatory Conformity",
        "Infrastructure and Cloud", "Hardware/Firmware", "Data/Workbook Systems",
        "Evidence, Assurance, and Deployment"
    }
    found = {item["display_name"] for item in portfolio["umbrellas"]}
    if found != expected:
        errors.append("portfolio_umbrella_set_mismatch")

    for document in (portfolio, naming, contracts, trajectory):
        if document.get("global_stop") is not False:
            errors.append("global_stop_must_be_false")

    ids = [item["id"] for item in portfolio["umbrellas"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_umbrella_identity")

    for item in portfolio["umbrellas"]:
        if item.get("inherits_common_substrate") is not True:
            errors.append("missing_common_substrate:" + item["display_name"])
        for field in ("id", "display_name", "slug", "owner", "native_field", "market_category", "regulatory_profile", "status"):
            if not item.get(field):
                errors.append("missing_portfolio_field:" + item.get("display_name", "unknown") + ":" + field)

    for entry in naming["entries"]:
        for field in naming["required_fields"]:
            if field not in entry:
                errors.append("missing_naming_field:" + entry.get("display_name", "unknown") + ":" + field)

    if len(contracts["contracts"]) < 6:
        errors.append("insufficient_bilateral_contracts")

    release_ids = {item["id"] for item in trajectory["release_trains"]}
    required_release_ids = {
        "RT0_PORTFOLIO_AUTHORITY", "RT1_COMMON_PLATFORM_ALPHA",
        "RT2_PRODUCTIVITY_AND_DATA_BETA", "RT3_REGULATED_WORKFLOW_PILOTS",
        "RT4_HARDWARE_AND_OEM", "RT5_ENTERPRISE_GA"
    }
    if release_ids != required_release_ids:
        errors.append("release_train_set_mismatch")

    return errors


if __name__ == "__main__":
    result = validate()
    print(json.dumps({"valid": not result, "errors": result}, indent=2))
    raise SystemExit(0 if not result else 1)
