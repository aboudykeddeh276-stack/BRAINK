#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

REQUIRED = {
    "schema",
    "component_id",
    "classification",
    "repository",
    "sector",
    "authority",
    "interfaces",
    "dependencies",
    "proof_conditions",
    "promotion_states",
}

DOCS = [
    "CONTROL_INDEX.md",
    "FILING_STANDARD.md",
    "SCHEMA_STANDARD.md",
    "AUTHORSHIP_AUTHORITY.md",
    "PROCESS_CONTROL.md",
    "WORKFLOW_CONTROL.md",
    "OPERATIONS_RUNBOOK.md",
    "CROSS_PLATFORM_CONTRACT.md",
    "ACCOUNTABILITY_EVIDENCE.md",
    "KEY_CONSIDERATIONS.md",
]


def _lines(items):
    return "\n".join(f"- {x}" for x in items) if items else "- None declared"


def validate(spec: dict) -> None:
    missing = sorted(REQUIRED - set(spec))
    if missing:
        raise ValueError(f"missing required specification fields: {missing}")
    if spec["schema"] != "kex.braink.governance-component-spec.v1":
        raise ValueError("unsupported governance specification schema")
    if not isinstance(spec["interfaces"], list) or not isinstance(spec["dependencies"], list):
        raise ValueError("interfaces and dependencies must be arrays")
    for edge in spec["dependencies"]:
        if edge.get("class") not in {
            "PACKAGE_DEPENDENCY",
            "MODULE_DEPENDENCY",
            "REPOSITORY_DEPENDENCY",
            "RUNTIME_AUTHORITY_DEPENDENCY",
        }:
            raise ValueError(f"invalid dependency class: {edge}")


def render(spec: dict) -> dict[str, str]:
    cid = spec["component_id"]
    name = spec.get("display_name", cid)
    owner = spec["authority"]["owner"]
    mutation = spec["authority"]["mutation_authority"]
    interfaces = [
        f"{x['name']}: {x['producer']} -> {x['consumer']} ({x.get('contract','contract not specified')})"
        for x in spec["interfaces"]
    ]
    dependencies = [f"{x['class']}: {x['target']}" for x in spec["dependencies"]]
    cross = spec.get("cross_platform", {})
    evidence = spec.get("evidence", {})

    docs: dict[str, str] = {}
    docs["CONTROL_INDEX.md"] = dedent(f"""\
    # {name} Control Index

    Component ID: `{cid}`  
    Classification: `{spec['classification']}`  
    Sector: `{spec['sector']}`  
    Repository: `{spec['repository']}`

    ## Authority
    Owner: `{owner}`  
    Mutation authority: `{mutation}`

    ## Interfaces
    {_lines(interfaces)}

    ## Control documents
    """) + _lines(DOCS[1:]) + "\n"

    docs["FILING_STANDARD.md"] = dedent(f"""\
    # Filing Standard

    Governed component: `{cid}`.

    Source paths:
    {_lines(spec.get('source_paths', []))}

    Evidence root: `{evidence.get('root','UNRESOLVED')}`.

    Rules:
    - source, configuration, runtime state and evidence are separate classes;
    - consequential receipts are append-only or uniquely versioned;
    - no secret/private-key bytes are committed to source control;
    - filenames do not substitute for schema identity;
    - every promoted artifact must resolve to repository + commit SHA + schema.
    """)

    docs["SCHEMA_STANDARD.md"] = dedent(f"""\
    # Schema Standard

    Governed component: `{cid}`.

    Required record envelope: schema, record_id, created_ns, repository, commit_sha,
    operation, status, authority, inputs, outputs, proof and rollback.

    Receipt schemas:
    {_lines(evidence.get('receipt_schemas', []))}

    Schema meaning may not change silently. Breaking semantic changes require a new schema version.
    """)

    docs["AUTHORSHIP_AUTHORITY.md"] = dedent(f"""\
    # Authorship and Authority

    `AUTHORSHIP != REPOSITORY OWNERSHIP != RUNTIME AUTHORITY != OPERATOR != EXTERNAL AUTHORITY`.

    Owner: `{owner}`  
    Mutation authority: `{mutation}`

    External authorities:
    {_lines(spec['authority'].get('external_authorities', []))}

    All consequential changes must be attributable to a commit SHA and runtime receipt lineage.
    """)

    docs["PROCESS_CONTROL.md"] = dedent(f"""\
    # Process Control

    Proof conditions:
    {_lines(spec['proof_conditions'])}

    Rollback requirements:
    {_lines(spec.get('rollback_requirements', []))}

    Promotion states:
    {_lines(spec['promotion_states'])}

    A stage may only be promoted when its declared proof conditions are observed.
    """)

    docs["WORKFLOW_CONTROL.md"] = dedent(f"""\
    # Workflow Control

    Required dependencies:
    {_lines(dependencies)}

    Workflow admission must resolve required dependencies before consequential mutation.
    Triggered, queued or pending workflow state is not execution proof.
    """)

    docs["OPERATIONS_RUNBOOK.md"] = dedent(f"""\
    # Operations Runbook

    1. Resolve exact repository SHA.
    2. Verify required dependencies and runtime authority.
    3. Execute pre-mutation qualification.
    4. Apply one controlled mutation.
    5. Read back through the consuming interface.
    6. Record receipt/evidence.
    7. Roll back on failed proof conditions.

    Operators:
    {_lines(spec.get('administration', {}).get('operators', []))}
    """)

    docs["CROSS_PLATFORM_CONTRACT.md"] = dedent(f"""\
    # Cross-Platform Contract

    Required capabilities:
    {_lines(cross.get('required_capabilities', []))}

    Platform-specific adapters:
    {_lines(cross.get('platform_specific_adapters', []))}

    Platform adaptation may replace carrier/substrate adapters while preserving component identity,
    interface semantics, authority rules, proof conditions and receipt schemas.
    """)

    docs["ACCOUNTABILITY_EVIDENCE.md"] = dedent(f"""\
    # Accountability and Evidence

    Each consequential operation must identify source SHA, actor/process, authority, input state,
    mutation, readback, proof class, status and rollback result.

    Evidence root: `{evidence.get('root','UNRESOLVED')}`.

    Invalid or incomplete evidence must not be promoted into a stronger capability claim.
    """)

    docs["KEY_CONSIDERATIONS.md"] = dedent(f"""\
    # Key Considerations

    Substrate boundary: `{spec.get('substrate_boundary','UNRESOLVED')}`  
    State class: `{spec.get('state_class','UNRESOLVED')}`  
    Persistence class: `{spec.get('persistence_class','UNRESOLVED')}`  
    Address space: `{spec.get('address_space','UNRESOLVED')}`  
    Virtualisation type: `{spec.get('virtualisation_type','UNRESOLVED')}`

    Communication mechanisms:
    {_lines(spec.get('communication_mechanisms', []))}

    Invalid claims:
    {_lines(spec.get('invalid_claims', []))}
    """)
    return docs


def manifest(spec: dict, docs: dict[str, str]) -> dict:
    return {
        "schema": "kex.braink.governance-manifest.v1",
        "component_id": spec["component_id"],
        "classification": spec["classification"],
        "repository": spec["repository"],
        "sector": spec["sector"],
        "authority": spec["authority"],
        "documents": sorted(docs),
        "dependencies": spec["dependencies"],
        "proof_conditions": spec["proof_conditions"],
        "promotion_states": spec["promotion_states"],
        "cross_platform": spec.get("cross_platform", {}),
        "evidence": spec.get("evidence", {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--force", action="store_true")
    ns = ap.parse_args()

    spec = json.loads(Path(ns.spec).read_text("utf-8"))
    validate(spec)
    out = Path(ns.output)
    out.mkdir(parents=True, exist_ok=True)
    docs = render(spec)
    docs["GOVERNANCE_MANIFEST.json"] = json.dumps(manifest(spec, docs), indent=2, sort_keys=True) + "\n"

    collisions = [name for name in docs if (out / name).exists()]
    if collisions and not ns.force:
        raise FileExistsError(f"refusing to overwrite existing controls: {collisions}")
    for name, content in docs.items():
        (out / name).write_text(content, "utf-8")
    print(json.dumps({"status": "GENERATED", "component_id": spec["component_id"], "files": sorted(docs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
