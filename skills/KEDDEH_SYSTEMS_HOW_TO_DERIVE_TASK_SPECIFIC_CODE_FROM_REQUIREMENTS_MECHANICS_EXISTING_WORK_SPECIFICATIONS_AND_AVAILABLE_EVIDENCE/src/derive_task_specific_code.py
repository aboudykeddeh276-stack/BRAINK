#!/usr/bin/env python3
"""
Task-Specific Code Derivation Engine
====================================
Reference implementation for the Keddeh Systems skill:

    KEDDEH_SYSTEMS_HOW_TO_DERIVE_TASK_SPECIFIC_CODE_FROM_REQUIREMENTS_MECHANICS_
    EXISTING_WORK_SPECIFICATIONS_AND_AVAILABLE_EVIDENCE

Governing object
----------------
The requirement is the *task-specific code* that implements a required capability.
The mechanics that causally produce that capability are the true highlights of the
function. Acquisition methods (repository, binary, package cache, download, ...)
exist only to supply the knowledge, source, reference implementations, or test
oracles required to derive and validate that code.

This engine is domain-general. It reasons over any capability specification that
follows the schema below. Bitcoin Core / BTC mining is provided as ONE amendable
case study under ``resources/`` — it is data consumed by this engine, not a locked
topic hard-coded into it.

Derivation hierarchy (the model this engine encodes)
----------------------------------------------------
    REQUIRED CAPABILITY
        -> REQUIRED MECHANICS
        -> REQUIRED CODE (functions)
        -> REQUIRED KNOWLEDGE / REFERENCE / TEST ORACLE
        -> DERIVATION PATHWAYS

    Download  (-)  Acquisition  (-)  Derivation Pathways

Governing rule (enforced by this engine)
----------------------------------------
    A failed acquisition method cannot be promoted into a capability limitation
    while other derivation pathways remain available or untested. A mechanic is
    only a capability limitation when EVERY pathway is exhausted with evidence
    (tested-and-failed or ruled-out-with-evidence). If any pathway is still
    untested, the status is EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN, not a limit.

Capability specification schema (JSON)
--------------------------------------
    {
      "capability": "<full semantic capability name>",
      "mechanics": [
        {
          "id": "<MACHINE_STABLE_ID>",
          "name": "<full semantic mechanic name>",
          "functions": [
            {
              "name": "...", "inputs": [...], "outputs": [...],
              "state": "...", "invariants": [...], "errors": [...],
              "interfaces": [...]
            }
          ],
          "required_knowledge": ["..."],
          "derivation_pathways": [
            {"kind": "<pathway kind>", "status": "<pathway status>",
             "evidence": "<optional evidence string>"}
          ]
        }
      ]
    }

Pathway kinds are open-ended, but a canonical ordering is defined in
``PATHWAY_PRIORITY`` so that acquisition (and download within it) sits at the
correct, subordinate level.

Usage
-----
    python3 derive_task_specific_code.py <capability_spec.json>
    python3 derive_task_specific_code.py --case-study btc
    python3 derive_task_specific_code.py --list-case-studies

Output (stdout)
---------------
    A JSON derivation report. Human-readable summary is written to stderr.

Exit codes
----------
    0   The capability is derivable (every mechanic has a live pathway).
    1   At least one mechanic is a proven capability limitation, OR the input
        could not be read/parsed.
    2   At least one mechanic has insufficient evidence (status unknown) and no
        mechanic is a proven limitation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"

# ---------------------------------------------------------------------------
# Pathway model
# ---------------------------------------------------------------------------
# The canonical priority ordering makes explicit that "download" is a subordinate
# route inside "acquisition", and acquisition is itself a subordinate class of the
# broader set of derivation pathways. Lower index == preferred / less costly /
# more authoritative-locally.
PATHWAY_PRIORITY: list[str] = [
    "already_local_module",          # previously verified module in this project
    "protocol_specification",        # derive mechanic from spec / mathematics
    "mathematical_derivation",
    "existing_source",               # source already present as source material
    "connected_repository",          # source reachable via connected repo
    "project_files",                 # source in current project files
    "package_manager_or_cache",      # acquisition: package cache
    "source_archive",                # acquisition
    "git_clone",                     # acquisition
    "binary_release",                # acquisition
    "download",                      # acquisition: a single subordinate operation
    "user_supplied_artifact",
    "published_test_vectors",        # test oracle
    "reference_implementation",      # differential oracle
    "independent_reimplementation",  # clean-room derivation as oracle
]

# The subset of pathway kinds that are acquisition operations. A failure limited
# to these must never, on its own, be promoted to a capability limitation.
ACQUISITION_PATHWAYS: frozenset[str] = frozenset(
    {
        "package_manager_or_cache",
        "source_archive",
        "git_clone",
        "binary_release",
        "download",
        "connected_repository",
        "user_supplied_artifact",
    }
)

# Pathway status vocabulary.
STATUS_AVAILABLE = "available"                     # usable now -> mechanic derivable
STATUS_UNTESTED = "untested"                       # plausible, not yet attempted
STATUS_TESTED_AND_FAILED = "tested_and_failed"     # attempted, failed, with evidence
STATUS_RULED_OUT = "ruled_out_with_evidence"       # excluded by a cited constraint

VALID_STATUSES: frozenset[str] = frozenset(
    {STATUS_AVAILABLE, STATUS_UNTESTED, STATUS_TESTED_AND_FAILED, STATUS_RULED_OUT}
)

# Exhausted-with-evidence statuses (a pathway that can no longer supply the source).
_EXHAUSTED = frozenset({STATUS_TESTED_AND_FAILED, STATUS_RULED_OUT})

# ---------------------------------------------------------------------------
# Mechanic derivation verdicts
# ---------------------------------------------------------------------------
MECHANIC_DERIVABLE = "MECHANIC_IS_DERIVABLE"
MECHANIC_STATUS_UNKNOWN = "EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN"
MECHANIC_LIMITATION = "CAPABILITY_LIMITATION_ALL_PATHWAYS_EXHAUSTED"


class SpecError(ValueError):
    """Raised when a capability specification is structurally invalid."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_spec(spec: Any) -> None:
    """Validate the structural contract of a capability specification.

    Raises SpecError with a precise message on the first violation.
    """
    if not isinstance(spec, dict):
        raise SpecError("capability specification must be a JSON object")
    if not isinstance(spec.get("capability"), str) or not spec["capability"].strip():
        raise SpecError("'capability' must be a non-empty string")
    mechanics = spec.get("mechanics")
    if not isinstance(mechanics, list) or not mechanics:
        raise SpecError("'mechanics' must be a non-empty list")

    seen_ids: set[str] = set()
    for index, mechanic in enumerate(mechanics):
        where = f"mechanics[{index}]"
        if not isinstance(mechanic, dict):
            raise SpecError(f"{where} must be an object")
        mech_id = mechanic.get("id")
        if not isinstance(mech_id, str) or not mech_id.strip():
            raise SpecError(f"{where}.id must be a non-empty string")
        if mech_id in seen_ids:
            raise SpecError(f"duplicate mechanic id '{mech_id}'")
        seen_ids.add(mech_id)
        if not isinstance(mechanic.get("name"), str) or not mechanic["name"].strip():
            raise SpecError(f"{where}.name must be a non-empty string")
        pathways = mechanic.get("derivation_pathways")
        if not isinstance(pathways, list) or not pathways:
            raise SpecError(f"{where}.derivation_pathways must be a non-empty list")
        for p_index, pathway in enumerate(pathways):
            p_where = f"{where}.derivation_pathways[{p_index}]"
            if not isinstance(pathway, dict):
                raise SpecError(f"{p_where} must be an object")
            if not isinstance(pathway.get("kind"), str) or not pathway["kind"].strip():
                raise SpecError(f"{p_where}.kind must be a non-empty string")
            status = pathway.get("status")
            if status not in VALID_STATUSES:
                raise SpecError(
                    f"{p_where}.status '{status}' is invalid; "
                    f"must be one of {sorted(VALID_STATUSES)}"
                )


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------
def _sorted_pathways(pathways: list[dict]) -> list[dict]:
    """Return pathways ordered by canonical priority, unknown kinds last."""
    def key(pathway: dict) -> tuple[int, str]:
        kind = pathway.get("kind", "")
        rank = PATHWAY_PRIORITY.index(kind) if kind in PATHWAY_PRIORITY else len(PATHWAY_PRIORITY)
        return (rank, kind)

    return sorted(pathways, key=key)


def evaluate_mechanic(mechanic: dict) -> dict:
    """Evaluate a single mechanic and return its derivation verdict.

    The verdict enforces the governing rule: a mechanic is a capability
    limitation ONLY when every pathway is exhausted with evidence. If any
    non-acquisition or acquisition pathway remains available -> derivable. If a
    pathway remains merely untested -> status unknown (never a limitation).
    """
    pathways = _sorted_pathways(mechanic["derivation_pathways"])

    available = [p for p in pathways if p["status"] == STATUS_AVAILABLE]
    untested = [p for p in pathways if p["status"] == STATUS_UNTESTED]
    exhausted = [p for p in pathways if p["status"] in _EXHAUSTED]

    selected_pathway = available[0] if available else None

    if available:
        verdict = MECHANIC_DERIVABLE
    elif untested:
        verdict = MECHANIC_STATUS_UNKNOWN
    else:
        verdict = MECHANIC_LIMITATION

    # Determine whether every *failed* pathway is an acquisition route. This is
    # the diagnostic that keeps a failed download from masquerading as a limit.
    failed_kinds = {p["kind"] for p in exhausted}
    failure_is_acquisition_only = bool(failed_kinds) and failed_kinds <= ACQUISITION_PATHWAYS

    return {
        "id": mechanic["id"],
        "name": mechanic["name"],
        "verdict": verdict,
        "selected_pathway": selected_pathway["kind"] if selected_pathway else None,
        "available_pathways": [p["kind"] for p in available],
        "untested_pathways": [p["kind"] for p in untested],
        "exhausted_pathways": [
            {"kind": p["kind"], "status": p["status"], "evidence": p.get("evidence", "")}
            for p in exhausted
        ],
        "failure_is_acquisition_only": failure_is_acquisition_only,
        "function_count": len(mechanic.get("functions", []) or []),
        "required_knowledge": list(mechanic.get("required_knowledge", []) or []),
    }


def derive(spec: dict) -> dict:
    """Produce a full derivation report for a capability specification."""
    validate_spec(spec)
    mechanic_reports = [evaluate_mechanic(m) for m in spec["mechanics"]]

    limitations = [m for m in mechanic_reports if m["verdict"] == MECHANIC_LIMITATION]
    unknowns = [m for m in mechanic_reports if m["verdict"] == MECHANIC_STATUS_UNKNOWN]
    derivable = [m for m in mechanic_reports if m["verdict"] == MECHANIC_DERIVABLE]

    if limitations:
        capability_verdict = "CAPABILITY_HAS_PROVEN_LIMITATION"
    elif unknowns:
        capability_verdict = "CAPABILITY_DERIVATION_STATUS_UNKNOWN_EVIDENCE_INSUFFICIENT"
    else:
        capability_verdict = "CAPABILITY_IS_FULLY_DERIVABLE"

    return {
        "capability": spec["capability"],
        "capability_verdict": capability_verdict,
        "mechanics": mechanic_reports,
        "summary": {
            "total_mechanics": len(mechanic_reports),
            "derivable": len(derivable),
            "status_unknown": len(unknowns),
            "proven_limitations": len(limitations),
        },
        "governing_rule": (
            "A failed acquisition method cannot be promoted into a capability "
            "limitation while other derivation pathways remain available or untested."
        ),
    }


def report_exit_code(report: dict) -> int:
    verdict = report["capability_verdict"]
    if verdict == "CAPABILITY_HAS_PROVEN_LIMITATION":
        return 1
    if verdict == "CAPABILITY_DERIVATION_STATUS_UNKNOWN_EVIDENCE_INSUFFICIENT":
        return 2
    return 0


# ---------------------------------------------------------------------------
# Case-study loading (amendable resources)
# ---------------------------------------------------------------------------
def list_case_studies() -> list[str]:
    if not RESOURCES_DIR.is_dir():
        return []
    return sorted(
        p.stem.replace("_case_study", "")
        for p in RESOURCES_DIR.glob("*_case_study.json")
    )


def load_case_study(name: str) -> dict:
    path = RESOURCES_DIR / f"{name}_case_study.json"
    if not path.is_file():
        available = ", ".join(list_case_studies()) or "(none)"
        raise SpecError(f"unknown case study '{name}'; available: {available}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _emit_human_summary(report: dict) -> None:
    icons = {
        MECHANIC_DERIVABLE: "OK ",
        MECHANIC_STATUS_UNKNOWN: "?? ",
        MECHANIC_LIMITATION: "XX ",
    }
    print(f"CAPABILITY: {report['capability']}", file=sys.stderr)
    for mechanic in report["mechanics"]:
        icon = icons.get(mechanic["verdict"], "?? ")
        route = mechanic["selected_pathway"] or "-"
        print(
            f"  {icon}[{mechanic['verdict']}] {mechanic['name']} "
            f"(route: {route})",
            file=sys.stderr,
        )
    print(f"VERDICT: {report['capability_verdict']}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate whether a required capability's task-specific code can be "
            "derived, treating acquisition (and download within it) as subordinate "
            "derivation pathways."
        )
    )
    parser.add_argument(
        "capability_spec",
        nargs="?",
        help="Path to a capability specification JSON file.",
    )
    parser.add_argument(
        "--case-study",
        help="Name of a bundled case study under resources/ (e.g. 'btc').",
    )
    parser.add_argument(
        "--list-case-studies",
        action="store_true",
        help="List available bundled case studies and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_case_studies:
        for name in list_case_studies():
            print(name)
        return 0

    try:
        if args.case_study:
            spec = load_case_study(args.case_study)
        elif args.capability_spec:
            spec = json.loads(Path(args.capability_spec).read_text(encoding="utf-8"))
        else:
            parser.error("provide a capability_spec path or --case-study NAME")
            return 1  # pragma: no cover - argparse exits first
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        report = derive(spec)
    except SpecError as exc:
        print(f"ERROR: invalid capability specification: {exc}", file=sys.stderr)
        return 1

    _emit_human_summary(report)
    print(json.dumps(report, indent=2))
    return report_exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
