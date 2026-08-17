#!/usr/bin/env python3
"""BRAINK/KEX proof-bearing repository command CLI.

Repositories are evidence-bearing engineering sectors, not product-state proxies.
This utility inventories local repositories and derives admissible next actions
from observed state without executing arbitrary repository code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GOVERNANCE_FILES = [
    "README.md", "LICENSE", ".gitignore",
    "docs/governance/repository-governance-standard.md",
    "docs/governance/manifest.json", "scripts/validate-governance.py",
    "scripts/bootstrap-general-governance.sh", "scripts/braink-agent-cli.py",
    "docs/governance/agentic-intelligence-cli.md",
    "docs/governance/strict-deep-analysis-comment.md",
]

EVIDENCE_STATES = {
    "UNKNOWN", "OBSERVED", "SOURCE_VERIFIED", "IMPLEMENTED", "TESTED",
    "VALIDATED", "INTEGRATION_CANDIDATE", "ACCEPTED", "DEPLOYED",
    "OPERATIONALLY_PROVEN", "INFERRED", "UNTESTED", "FAILED", "BLOCKED",
    "SUPERSEDED", "HISTORICAL", "RECONSTRUCTED_FROM_CURRENT_LINEAGE",
}

@dataclass(frozen=True)
class RepositorySignal:
    path: str
    name: str
    branch: str
    head: str
    dirty: bool
    governance_files_present: list[str]
    governance_files_missing: list[str]
    observed_state: str
    evidence_state: str

@dataclass(frozen=True)
class CommandPacket:
    command_id: str
    intent: str
    requirement: str
    observed_state: str
    authority: str
    invariant: str
    expected_effect: str
    test_method: str
    promotion_criterion: str
    admissible: bool
    blockers: list[str]
    next_valid_routes: list[str]


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=False, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return "UNKNOWN" if result.returncode != 0 else result.stdout.strip()


def discover_repositories(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repository root does not exist or is not a directory: {root}")
    return sorted({git_dir.parent for git_dir in root.rglob(".git") if git_dir.is_dir()})


def inspect_repository(repo: Path) -> RepositorySignal:
    present = [p for p in GOVERNANCE_FILES if (repo / p).exists()]
    missing = [p for p in GOVERNANCE_FILES if p not in present]
    dirty = bool(run_git(repo, ["status", "--porcelain=v1"]))
    branch = run_git(repo, ["branch", "--show-current"]) or "DETACHED"
    head = run_git(repo, ["rev-parse", "--short", "HEAD"]) or "UNKNOWN"
    observed = "STATE_MODEL_LOCAL" if not missing else "STATE_PENDING"
    evidence = "SOURCE_VERIFIED" if head != "UNKNOWN" else "OBSERVED"
    return RepositorySignal(str(repo), repo.name, branch, head, dirty, present, missing, observed, evidence)


def canonical_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def derive_routes(signal: RepositorySignal) -> list[str]:
    routes: list[str] = []
    if signal.governance_files_missing:
        routes.append("VERIFY_AND_REPAIR_GOVERNANCE_BASELINE")
    if signal.dirty:
        routes.append("INSPECT_UNCOMMITTED_STATE_BEFORE_CHANGE")
    if signal.head == "UNKNOWN":
        routes.append("RESOLVE_REPOSITORY_IDENTITY")
    if not routes:
        routes.extend(["LOCATE_EXISTING_MECHANIC", "DERIVE_BOUNDED_CHANGE", "RUN_ALLOWLISTED_TEST"])
    return routes


def packet_for(signal: RepositorySignal, intent: str) -> CommandPacket:
    blockers = []
    if signal.head == "UNKNOWN": blockers.append("BLOCKED_REPOSITORY_HEAD_UNKNOWN")
    if signal.governance_files_missing: blockers.append("BLOCKED_GOVERNANCE_BASELINE_INCOMPLETE")
    routes = derive_routes(signal)
    raw_id = f"{signal.path}|{signal.head}|{intent}|{'|'.join(routes)}"
    command_id = hashlib.sha256(raw_id.encode()).hexdigest()[:16]
    return CommandPacket(
        command_id=command_id,
        intent=intent,
        requirement="Advance the stated objective without treating repository mutation as product progress.",
        observed_state=signal.evidence_state,
        authority="LOCAL_READ_AND_ALLOWLISTED_VERIFICATION_ONLY",
        invariant="PRESERVE_WORKING_CODE_AND_LINEAGE_UNTIL_EVIDENCE_JUSTIFIES_PROMOTION",
        expected_effect="Produce evidence sufficient to derive the next admissible engineering transition.",
        test_method="Read back state, execute only an explicitly allowlisted verification, classify result.",
        promotion_criterion="Required test evidence exists and affected invariants remain satisfied.",
        admissible=not blockers,
        blockers=blockers,
        next_valid_routes=routes,
    )


def build_agent_plan(signals: list[RepositorySignal], intent: str) -> dict[str, Any]:
    packets = [asdict(packet_for(s, intent)) for s in signals]
    payload: dict[str, Any] = {
        "WHOLE_NAME": "WHOLE_BRAINK_PROOF_BEARING_COMMAND_RUNTIME",
        "WHOLE_OWNER_LINEAGE": "a.keddeh",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "intent": intent,
        "repos_discovered": len(signals),
        "repositories": [asdict(s) for s in signals],
        "command_packets": packets,
        "execution_law": ["INTENT", "VERIFY_ACTUAL_STATE", "LOCATE_EXISTING_MECHANIC",
                          "RESOLVE_REAL_DEPENDENCY", "EXECUTE_BOUNDED_ACTION", "READ_BACK",
                          "CLASSIFY_EVIDENCE", "FOLLOW_DESCENDANTS", "DERIVE_NEXT_ROUTE"],
        "evidence_vocabulary": sorted(EVIDENCE_STATES),
        "boundary": "Planning and read-only inspection do not constitute product completion.",
    }
    payload["proof_sha256"] = canonical_hash(payload)
    return payload


def command_scan(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).expanduser().resolve()
    try: signals = [inspect_repository(r) for r in discover_repositories(root)]
    except ValueError as exc:
        print(f"BRAINK_AGENT_CLI_ERROR: {exc}", file=sys.stderr); return 2
    print(json.dumps(build_agent_plan(signals, args.intent), indent=2, sort_keys=True)); return 0


def command_plan(args: argparse.Namespace) -> int:
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / ".git").is_dir():
        print("BRAINK_AGENT_CLI_ERROR: target is not a git repository", file=sys.stderr); return 2
    signal = inspect_repository(repo)
    payload = {"repository": asdict(signal), "command_packet": asdict(packet_for(signal, args.intent))}
    payload["proof_sha256"] = canonical_hash(payload)
    print(json.dumps(payload, indent=2, sort_keys=True)); return 0


def command_status(_: argparse.Namespace) -> int:
    print("BRAINK_AGENT_CLI_STATUS: PROOF_BEARING_PLANNER_AVAILABLE")
    print("BRAINK_AGENT_CLI_BOUNDARY: no arbitrary repository code execution")
    print("BRAINK_AGENT_CLI_RULE: commit != completion; promotion requires evidence")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="braink-agent-cli", description="BRAINK/KEX proof-bearing command planner.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Inventory repositories and derive admissible routes.")
    scan.add_argument("--repo-root", default=".")
    scan.add_argument("--intent", default="INSPECT_AND_DERIVE_NEXT_VALID_ENGINEERING_ACTION")
    scan.set_defaults(func=command_scan)
    plan = sub.add_parser("plan", help="Derive a proof-bearing command packet for one repository.")
    plan.add_argument("--repo", default=".")
    plan.add_argument("--intent", required=True)
    plan.set_defaults(func=command_plan)
    status = sub.add_parser("status", help="Print runtime boundary and status.")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
