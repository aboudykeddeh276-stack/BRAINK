#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PRODUCT_VERSION = "0.1.0-mmp"
PROJECT_FORMAT_VERSION = "1.0.0"
SUPPORTED_PROFILES = ("server", "bios-firmware", "hardware-abstraction")
REQUIRED_FILES = (
    "keo.project.json",
    "kir.json",
    "topology.json",
    "iteration.json",
    "PRODUCT_STATE.md",
    "README.md",
)
IDENTITY_PATTERN = re.compile(r"^[a-z][a-z0-9-]*://[a-z0-9-]+(?:/[a-z0-9-]+)*$")


class KeoError(RuntimeError):
    pass


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def profile_contract(profile: str, project_slug: str) -> dict[str, Any]:
    system_id = f"system://{project_slug}"
    if profile == "server":
        return {
            "system_id": system_id,
            "purpose": "Versioned network service with explicit protocol, state, failure, and deployment contracts.",
            "domains": ["request-ingress", "application-core", "persistence", "operations"],
            "interfaces": ["interface://network/request/v1", "interface://operations/health/v1"],
            "execution_targets": ["server-process", "container", "microVM"],
            "obligations": ["protocol", "concurrency", "persistence", "authentication", "observability", "recovery"],
        }
    if profile == "bios-firmware":
        return {
            "system_id": system_id,
            "purpose": "Freestanding firmware with explicit reset, memory, platform initialisation, boot handoff, and recovery contracts.",
            "domains": ["reset-entry", "platform-init", "memory-discovery", "device-init", "boot-handoff", "recovery"],
            "interfaces": ["interface://firmware/reset/v1", "interface://firmware/boot-handoff/v1"],
            "execution_targets": ["raw-processor", "BIOS-or-UEFI-firmware", "simulator"],
            "obligations": ["processor-architecture", "reset-vector", "linker-layout", "memory-map", "interrupts", "debug-anchor", "recovery"],
        }
    if profile == "hardware-abstraction":
        return {
            "system_id": system_id,
            "purpose": "Stable software-visible hardware capability contract with simulated, virtual, FPGA, ASIC, or physical backing.",
            "domains": ["capability-contract", "register-model", "bus-protocol", "interrupt-events", "backing-adapters", "readback"],
            "interfaces": ["interface://hardware/capability/v1", "interface://hardware/readback/v1"],
            "execution_targets": ["simulator", "microVM", "FPGA", "ASIC", "raw-processor"],
            "obligations": ["registers", "buses", "interrupts", "timing", "ordering", "backing-class", "readback"],
        }
    raise KeoError(f"unsupported profile: {profile}")


def build_project_payload(name: str, slug: str, profile: str) -> dict[str, Any]:
    return {
        "project_format_version": PROJECT_FORMAT_VERSION,
        "product": "KEDDEH Engineering Orchestrator",
        "product_version": PRODUCT_VERSION,
        "project_name": name,
        "project_slug": slug,
        "profile": profile,
        "system_id": f"system://{slug}",
        "privacy_mode": "LOCAL_ONLY_NO_SOURCE_UPLOAD",
        "global_stop": False,
    }


def build_kir_payload(name: str, slug: str, profile: str) -> dict[str, Any]:
    contract = profile_contract(profile, slug)
    return {
        "kir_id": f"ir://{slug}/system-synthesis",
        "version": "1.0.0",
        "system_id": contract["system_id"],
        "name": name,
        "profile": profile,
        "planes": {
            "identity_plane": {"status": "DEFINED", "objects": [contract["system_id"]]},
            "semantic_plane": {"status": "DEFINED", "purpose": contract["purpose"]},
            "topology_plane": {"status": "DEFINED", "domains": contract["domains"]},
            "state_plane": {"status": "REQUIRES_DESIGN", "state_machines": []},
            "data_plane": {"status": "REQUIRES_DESIGN", "schemas": []},
            "execution_plane": {"status": "DEFINED", "targets": contract["execution_targets"]},
            "hardware_plane": {"status": "REQUIRES_DESIGN", "contracts": []},
            "policy_plane": {"status": "DEFINED", "privacy": "LOCAL_ONLY_NO_SOURCE_UPLOAD"},
            "evidence_plane": {"status": "REQUIRES_EXECUTION", "evidence_refs": []},
        },
        "interfaces": contract["interfaces"],
        "obligations": contract["obligations"],
        "promotion_state": "FORMALISED",
        "global_stop": False,
    }


def build_topology_payload(slug: str, profile: str) -> dict[str, Any]:
    contract = profile_contract(profile, slug)
    nodes: list[dict[str, Any]] = [
        {
            "identity": contract["system_id"],
            "level": "L1_SYSTEM",
            "kind": "system",
            "name": slug,
            "responsibility": contract["purpose"],
            "owner": "UNASSIGNED",
            "status": "ACTIVE",
        }
    ]
    edges: list[dict[str, Any]] = []
    for domain_name in contract["domains"]:
        domain_id = f"domain://{slug}/{domain_name}"
        nodes.append({
            "identity": domain_id,
            "level": "L2_DOMAIN",
            "kind": "domain",
            "name": domain_name,
            "responsibility": f"Own the {domain_name} responsibility boundary.",
            "owner": "UNASSIGNED",
            "status": "PLANNED",
        })
        edges.append({
            "source": contract["system_id"],
            "target": domain_id,
            "relationship": "CONTAINS",
            "capability": domain_name,
            "data": [],
            "criticality": "REQUIRED",
            "failure_impact_radius": [domain_id],
        })
    return {
        "topology_id": f"topology://{slug}/canonical",
        "system_id": contract["system_id"],
        "version": "1.0.0",
        "nodes": nodes,
        "edges": edges,
        "views": [
            "CONTEXT_VIEW",
            "BUILDING_BLOCK_VIEW",
            "RUNTIME_VIEW",
            "DEPLOYMENT_VIEW",
            "DATA_LINEAGE_VIEW",
            "FAILURE_AND_RECOVERY_VIEW",
            "SECURITY_AND_TRUST_VIEW",
            "EVIDENCE_AND_PROMOTION_VIEW",
        ],
        "adrs": [],
        "iteration_id": f"iteration://{slug}/0001",
        "validation_gates": ["GATE_TOPOLOGY_01_IDENTITIES_UNIQUE", "GATE_TOPOLOGY_03_RELATIONSHIPS_LABELLED"],
        "artifact_state": "DURABLE_NATIVE_RECORD",
        "promotion_state": "FORMALISED",
        "global_stop": False,
    }


def build_iteration_payload(slug: str) -> dict[str, Any]:
    return {
        "iteration_id": f"iteration://{slug}/0001",
        "current_state": "I2_DESIGN",
        "completed_states": ["I0_OBSERVE", "I1_DEFINE"],
        "objective": "Complete topology, interfaces, implementation plan, and proof obligations for the selected profile.",
        "required_outputs": ["topology_delta", "interface_contracts", "ADRs", "risk_register"],
        "remaining_gates": ["I3_IMPLEMENT", "I4_STATIC_VALIDATE", "I5_EXECUTE", "I6_INTEGRATE", "I7_PROMOTE", "I8_PRESERVE", "I9_REVIEW"],
        "global_stop": False,
    }


def command_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).resolve()
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
    if not slug or not re.fullmatch(r"[a-z][a-z0-9-]*", slug):
        raise KeoError("project slug must use lower-kebab-case and begin with a letter")
    if args.profile not in SUPPORTED_PROFILES:
        raise KeoError(f"profile must be one of: {', '.join(SUPPORTED_PROFILES)}")
    if target.exists() and any(target.iterdir()) and not args.force:
        raise KeoError(f"target directory is not empty: {target}; use --force only when overwriting is intended")
    target.mkdir(parents=True, exist_ok=True)

    write_json(target / "keo.project.json", build_project_payload(args.name, slug, args.profile))
    write_json(target / "kir.json", build_kir_payload(args.name, slug, args.profile))
    write_json(target / "topology.json", build_topology_payload(slug, args.profile))
    write_json(target / "iteration.json", build_iteration_payload(slug))
    (target / "PRODUCT_STATE.md").write_text(
        f"# Product State — {args.name}\n\n"
        f"- Profile: `{args.profile}`\n"
        f"- System: `system://{slug}`\n"
        "- Current iteration: `I2_DESIGN`\n"
        "- Promotion state: `FORMALISED`\n"
        "- Privacy: `LOCAL_ONLY_NO_SOURCE_UPLOAD`\n"
        "- Global stop: `false`\n",
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        f"# {args.name}\n\n"
        "This project was initialised by KEDDEH Engineering Orchestrator.\n\n"
        "## Next commands\n\n"
        "```bash\n"
        f"python3 keo.py validate {target}\n"
        f"python3 keo.py inspect {target}\n"
        "```\n\n"
        "Complete the KIR state, data, hardware, and evidence planes before promotion.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "INITIALISED", "directory": str(target), "profile": args.profile, "system_id": f"system://{slug}"}, indent=2))
    return 0


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KeoError(f"missing required file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise KeoError(f"invalid JSON in {path.name}: line {exc.lineno}, column {exc.colno}") from exc


def validate_project(directory: Path) -> list[str]:
    errors: list[str] = []
    for filename in REQUIRED_FILES:
        if not (directory / filename).exists():
            errors.append(f"missing:{filename}")
    if errors:
        return errors

    project = load_json_file(directory / "keo.project.json")
    kir = load_json_file(directory / "kir.json")
    topology = load_json_file(directory / "topology.json")
    iteration = load_json_file(directory / "iteration.json")

    if project.get("profile") not in SUPPORTED_PROFILES:
        errors.append("project:unsupported_profile")
    if project.get("global_stop") is not False:
        errors.append("project:global_stop_must_be_false")
    system_id = project.get("system_id", "")
    if not isinstance(system_id, str) or not IDENTITY_PATTERN.fullmatch(system_id):
        errors.append("project:invalid_system_id")
    if kir.get("system_id") != system_id:
        errors.append("kir:system_identity_mismatch")
    if topology.get("system_id") != system_id:
        errors.append("topology:system_identity_mismatch")
    if topology.get("iteration_id") != iteration.get("iteration_id"):
        errors.append("iteration:identity_mismatch")
    if kir.get("global_stop") is not False or topology.get("global_stop") is not False or iteration.get("global_stop") is not False:
        errors.append("contract:global_stop_must_be_false")

    node_ids = [node.get("identity") for node in topology.get("nodes", [])]
    if len(node_ids) != len(set(node_ids)):
        errors.append("topology:duplicate_node_identity")
    known_ids = set(node_ids)
    for index, edge in enumerate(topology.get("edges", [])):
        if edge.get("source") not in known_ids:
            errors.append(f"topology:edge_{index}:unknown_source")
        if edge.get("target") not in known_ids:
            errors.append(f"topology:edge_{index}:unknown_target")
        if not edge.get("relationship"):
            errors.append(f"topology:edge_{index}:missing_relationship")
        if not edge.get("failure_impact_radius"):
            errors.append(f"topology:edge_{index}:missing_failure_impact_radius")

    required_planes = {
        "identity_plane", "semantic_plane", "topology_plane", "state_plane", "data_plane",
        "execution_plane", "hardware_plane", "policy_plane", "evidence_plane",
    }
    if set(kir.get("planes", {})) != required_planes:
        errors.append("kir:incomplete_plane_set")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    directory = Path(args.directory).resolve()
    errors = validate_project(directory)
    result = {"status": "PASS" if not errors else "FAIL", "directory": str(directory), "errors": errors}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_inspect(args: argparse.Namespace) -> int:
    directory = Path(args.directory).resolve()
    errors = validate_project(directory)
    if errors:
        print(json.dumps({"status": "INVALID", "errors": errors}, indent=2))
        return 1
    project = load_json_file(directory / "keo.project.json")
    kir = load_json_file(directory / "kir.json")
    topology = load_json_file(directory / "topology.json")
    iteration = load_json_file(directory / "iteration.json")
    summary = {
        "status": "VALID",
        "project": project["project_name"],
        "profile": project["profile"],
        "system_id": project["system_id"],
        "topology_nodes": len(topology["nodes"]),
        "topology_edges": len(topology["edges"]),
        "interfaces": kir["interfaces"],
        "current_iteration_state": iteration["current_state"],
        "promotion_state": kir["promotion_state"],
        "privacy_mode": project["privacy_mode"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keo", description="KEDDEH Engineering Orchestrator local CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Initialise a KEO engineering project")
    init_parser.add_argument("directory")
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--slug")
    init_parser.add_argument("--profile", required=True, choices=SUPPORTED_PROFILES)
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(handler=command_init)

    validate_parser = sub.add_parser("validate", help="Validate a KEO project contract")
    validate_parser.add_argument("directory")
    validate_parser.set_defaults(handler=command_validate)

    inspect_parser = sub.add_parser("inspect", help="Inspect a valid KEO project")
    inspect_parser.add_argument("directory")
    inspect_parser.set_defaults(handler=command_inspect)

    profiles_parser = sub.add_parser("profiles", help="List starter engineering profiles")
    profiles_parser.set_defaults(handler=lambda _: print("\n".join(SUPPORTED_PROFILES)) or 0)

    version_parser = sub.add_parser("version", help="Print product version")
    version_parser.set_defaults(handler=lambda _: print(PRODUCT_VERSION) or 0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except KeoError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
