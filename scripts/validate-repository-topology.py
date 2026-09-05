#!/usr/bin/env python3
"""Fail-closed validator for the KEX/BRAINK repository topology inventory."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "governance" / "repository-topology-v1.json"

ALLOWED_LAYERS = {
    "governance", "substrate", "runtime", "application", "interface",
    "verification", "research", "infrastructure", "education", "unclassified"
}


def main() -> int:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    repos = data.get("classification")
    authority = data.get("authority", {})

    if not isinstance(repos, list) or not repos:
        raise SystemExit("FAIL: classification must be a non-empty list")

    names = [r.get("name") for r in repos]
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise SystemExit("FAIL: every repository must have a non-empty name")
    if len(names) != len(set(names)):
        raise SystemExit("FAIL: duplicate repository identity in inventory")

    observed = authority.get("observed_repository_count")
    classified = authority.get("classified_repository_count")
    if observed != len(repos) or classified != len(repos):
        raise SystemExit(
            f"FAIL: count mismatch observed={observed} classified={classified} records={len(repos)}"
        )

    for repo in repos:
        if repo.get("layer") not in ALLOWED_LAYERS:
            raise SystemExit(f"FAIL: invalid layer for {repo.get('name')!r}")
        if not repo.get("role") or not repo.get("risk"):
            raise SystemExit(f"FAIL: incomplete classification for {repo.get('name')!r}")

    rules = data.get("rules", {})
    required_rules = {
        "identity_precedes_merge",
        "capability_precedes_new_repository",
        "duplicate_functions_are_canonicalized_before_expansion",
        "orphan_repositories_are_not_deleted_without_lineage_review",
        "experimental_code_requires_tests_before_promotion",
        "production_authority_must_be_explicit",
        "public_claims_require_external_evidence",
        "repository_name_never_overrides_observed_content",
    }
    missing = sorted(k for k in required_rules if rules.get(k) is not True)
    if missing:
        raise SystemExit("FAIL: required fail-closed rules missing: " + ", ".join(missing))

    print(f"PASS: repository topology inventory valid ({len(repos)} repositories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
