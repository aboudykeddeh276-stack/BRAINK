#!/usr/bin/env python3
"""BRAINK/KEX agentic repository CLI.

This tool is a local, defensive programmer/intelligence utility. It inventories
repositories, classifies their governance readiness, and emits a deterministic
plan for using repositories as inputs to a CLI/agent/augmented-intelligence
software stack. It does not execute arbitrary code from discovered repositories.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

GOVERNANCE_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "docs/governance/repository-governance-standard.md",
    "docs/governance/manifest.json",
    "scripts/validate-governance.py",
    "scripts/bootstrap-general-governance.sh",
    "scripts/braink-agent-cli.py",
    "docs/governance/agentic-intelligence-cli.md",
]


@dataclass(frozen=True)
class RepositorySignal:
    path: str
    name: str
    branch: str
    head: str
    dirty: bool
    governance_files_present: list[str]
    governance_files_missing: list[str]
    state: str


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


def discover_repositories(root: Path) -> list[Path]:
    repositories: list[Path] = []
    for git_dir in root.rglob(".git"):
        if git_dir.is_dir():
            repositories.append(git_dir.parent)
    return sorted(set(repositories))


def inspect_repository(repo: Path) -> RepositorySignal:
    present = [relative for relative in GOVERNANCE_FILES if (repo / relative).exists()]
    missing = [relative for relative in GOVERNANCE_FILES if relative not in present]
    dirty = bool(run_git(repo, ["status", "--porcelain=v1"]))
    state = "STATE_MODEL_LOCAL" if not missing else "STATE_PENDING"
    return RepositorySignal(
        path=str(repo),
        name=repo.name,
        branch=run_git(repo, ["branch", "--show-current"]),
        head=run_git(repo, ["rev-parse", "--short", "HEAD"]),
        dirty=dirty,
        governance_files_present=present,
        governance_files_missing=missing,
        state=state,
    )


def build_agent_plan(signals: list[RepositorySignal]) -> dict[str, object]:
    return {
        "WHOLE_NAME": "WHOLE_BRAINK_AGENTIC_INTELLIGENCE_CLI",
        "WHOLE_OWNER_LINEAGE": "a.keddeh",
        "GOVERNANCE_ROOT": "GENERAL-GOVERNANCE-",
        "REPOSITORY_FUNCTION": "FUNCTION_INVENTORY_REPOSITORIES_AND_PLAN_AGENTIC_PROGRAMMER_INPUTS",
        "REPOSITORY_ENVIRONMENT": "ENVIRONMENT_LOCAL_DEVELOPMENT",
        "REPOSITORY_STATE": "STATE_MODEL_LOCAL",
        "repos_discovered": len(signals),
        "repositories": [asdict(signal) for signal in signals],
        "agentic_routes": [
            "FUNCTION_SCAN_REPOSITORIES",
            "FUNCTION_CLASSIFY_GOVERNANCE_READINESS",
            "FUNCTION_PLAN_CLI_AGENT_AUGMENTED_INTELLIGENCE_INPUTS",
            "FUNCTION_REPORT_PENDING_EXTERNAL_ADOPTION",
        ],
        "pending_gates": [
            "PENDING_EXTERNAL_REPOSITORY_ACCESS_FOR_REPOS_NOT_PRESENT_LOCALLY",
            "PENDING_AUTHENTICATED_REMOTE_FETCH_OR_PUSH",
            "PENDING_DOWNSTREAM_REPOSITORY_VALIDATOR_EXECUTION",
        ],
    }


def command_scan(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).expanduser().resolve()
    signals = [inspect_repository(repo) for repo in discover_repositories(root)]
    print(json.dumps(build_agent_plan(signals), indent=2, sort_keys=True))
    return 0


def command_status(_: argparse.Namespace) -> int:
    print("BRAINK_AGENT_CLI_STATUS: COMPLETED")
    print("BRAINK_AGENT_CLI_MODE: MODEL_LOCAL")
    print("BRAINK_AGENT_CLI_BOUNDARY: no arbitrary repository code execution")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="braink-agent-cli",
        description="BRAINK/KEX local agentic repository programmer and augmented-intelligence CLI.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser("scan", help="Inventory local repositories and produce an agentic plan.")
    scan.add_argument("--repo-root", default=".", help="Directory to search for git repositories. Defaults to current directory.")
    scan.set_defaults(func=command_scan)

    status = subcommands.add_parser("status", help="Print CLI boundary and local status.")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
