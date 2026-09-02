#!/usr/bin/env python3
"""KEDDEH Systems canonical sector repository creation + bootstrap actuator.

Creates missing sector repositories through the GitHub REST API, bootstraps the
sector authority skeleton, and independently reads every created/observed file
back before reporting completion.

Credential contract: supply a repository-creation-capable token via GITHUB_TOKEN
(or --token-env). Never place credentials in source or repository files.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Iterable

API = "https://api.github.com"
DEFAULT_OWNER = "aboudykeddeh276-stack"
SECTORS = {
    "KEX": "Coordinate addressing, execution semantics, signal propagation and kernel mechanics.",
    "DOMAIN-AUTHORITY": "Registrar state, zones, DNS authority contracts, delegation tooling and DNSSEC evidence.",
    "NETWORK-FABRIC": "Routing, bridges, mesh, VPN/TL transports, NAT, anycast and load balancing.",
    "CLOUD-INFRASTRUCTURE": "Public compute hosts, VPS/runtime allocation and edge/cloud substrate authority.",
    "K-DRIVE": "Substrate-independent storage classes, volumes, persistence and VFS mechanics.",
    "IL-LLM": "Language/runtime model, dictionaries, ontology and IL-LLM mechanics.",
    "WORKBOOK-OS": "Workbook-native execution, scheduler, ledgers and sheet/runtime bindings.",
    "CASEPATH": "CasePath product, runtime and service pipeline only.",
    "CLAIMPATH": "ClaimPath product, runtime and service pipeline only.",
    "WEB-FABRIC": "Public web frontages, site deployment surfaces and domain-to-site projection.",
    "EDGE-IOT": "IoT edge nodes, telemetry, constrained runtimes and Observer² edge probes.",
    "SECURITY-AUTHORITY": "Identity, cryptographic policy, certificates, trust anchors and audit rules.",
    "AGENTS-ORCHESTRATION": "Agents, superagents, operator routing, workforce and process orchestration.",
    "EVIDENCE-LEDGER": "Qualification evidence, receipts, benchmarks, readbacks and conformance reports.",
}
CANONICAL_SECTOR_REPOS = tuple(SECTORS)


class GitHubAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepoResult:
    name: str
    full_name: str
    repository_status: str
    bootstrap_status: str
    readback_status: str
    html_url: str | None
    private: bool | None


class GitHubRepoCreator:
    def __init__(self, token: str, owner: str, timeout: float = 20.0):
        if not token:
            raise ValueError("GitHub token is required")
        self.token = token
        self.owner = owner
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            API + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "KEX-BRAINK-Repo-Creator/2.0",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"message": raw}
            if exc.code == 404:
                return 404, parsed
            if exc.code == 422:
                return 422, parsed
            raise GitHubAPIError(f"GitHub API {exc.code}: {parsed.get('message', raw)}") from exc
        except urllib.error.URLError as exc:
            raise GitHubAPIError(f"GitHub transport failure: {exc.reason}") from exc

    def authenticated_login(self) -> str:
        status, data = self._request("GET", "/user")
        if status != 200 or not data.get("login"):
            raise GitHubAPIError("Unable to resolve authenticated GitHub identity")
        return str(data["login"])

    def get_repo(self, name: str) -> dict | None:
        owner = urllib.parse.quote(self.owner, safe="")
        repo = urllib.parse.quote(name, safe="")
        status, data = self._request("GET", f"/repos/{owner}/{repo}")
        return None if status == 404 else data

    def _contents_path(self, name: str, path: str) -> str:
        owner = urllib.parse.quote(self.owner, safe="")
        repo = urllib.parse.quote(name, safe="")
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        return f"/repos/{owner}/{repo}/contents/{encoded_path}"

    def get_file(self, name: str, path: str) -> dict | None:
        status, data = self._request("GET", self._contents_path(name, path))
        return None if status == 404 else data

    def create_file_if_missing(self, name: str, path: str, content: str, message: str) -> str:
        existing = self.get_file(name, path)
        if existing:
            return "EXISTS"
        status, data = self._request("PUT", self._contents_path(name, path), {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        })
        if status not in (200, 201):
            raise GitHubAPIError(f"Failed to create {name}:{path}, status={status}, response={data}")
        if not self.get_file(name, path):
            raise GitHubAPIError(f"Readback failed for {name}:{path}")
        return "CREATED_AND_READ_BACK"

    def ensure_repo(self, name: str, *, private: bool) -> tuple[dict, str]:
        existing = self.get_repo(name)
        if existing:
            return existing, "EXISTS"
        login = self.authenticated_login()
        payload = {
            "name": name,
            "description": f"Canonical KEDDEH Systems sector repository: {name}",
            "private": private,
            "auto_init": True,
            "has_issues": True,
            "has_projects": True,
            "has_wiki": False,
        }
        if self.owner == login:
            path = "/user/repos"
        else:
            owner = urllib.parse.quote(self.owner, safe="")
            path = f"/orgs/{owner}/repos"
        status, data = self._request("POST", path, payload)
        if status not in (201, 202):
            raise GitHubAPIError(f"Unexpected create status {status} for {name}: {data}")
        observed = self.get_repo(name)
        if not observed:
            raise GitHubAPIError(f"Repository {self.owner}/{name} was not observable after creation")
        return observed, "CREATED_AND_READ_BACK"

    @staticmethod
    def bootstrap_files(name: str) -> dict[str, str]:
        purpose = SECTORS[name]
        header = f"# {name}\n\nCanonical KEDDEH Systems sector repository.\n\n"
        return {
            "README.md": header + f"## Purpose\n\n{purpose}\n\n## Governance\n\nSee `AUTHORITY.md`, `ARCHITECTURE.md`, and `DEPENDENCIES.md`.\n",
            "AUTHORITY.md": header + f"## Owns\n\n{purpose}\n\n## Authority rule\n\nThis repository is authoritative only for this sector. Cross-sector dependencies are relations, not interchangeable implementations. No completion claim is valid without execution/readback evidence.\n",
            "ARCHITECTURE.md": header + "## Required execution chain\n\n`SOURCE -> ADMISSION -> EXECUTION/ACTUATION -> OBSERVER² READBACK -> EVIDENCE -> CONTINUATION`\n\nCandidate/mirror state is non-authoritative until environmental readback substantiates mutation.\n",
            "DEPENDENCIES.md": header + "## Dependency contract\n\nDependencies must resolve to canonical sector repositories. Copying a mechanic does not transfer sector authority.\n",
            "runtime/.gitkeep": "",
            "tests/.gitkeep": "",
            "deploy/.gitkeep": "",
            "evidence/.gitkeep": "",
            "receipts/.gitkeep": "",
            "docs/.gitkeep": "",
        }

    def create_and_bootstrap(self, name: str, *, private: bool) -> RepoResult:
        observed, repo_status = self.ensure_repo(name, private=private)
        statuses = []
        for path, content in self.bootstrap_files(name).items():
            statuses.append(self.create_file_if_missing(
                name, path, content,
                f"bootstrap canonical {name} sector: {path}",
            ))
        required = tuple(self.bootstrap_files(name))
        missing = [path for path in required if not self.get_file(name, path)]
        if missing:
            raise GitHubAPIError(f"Bootstrap readback incomplete for {name}: {missing}")
        return RepoResult(
            name=name,
            full_name=str(observed.get("full_name", f"{self.owner}/{name}")),
            repository_status=repo_status,
            bootstrap_status="COMPLETE" if all(s in {"EXISTS", "CREATED_AND_READ_BACK"} for s in statuses) else "INCOMPLETE",
            readback_status="VERIFIED",
            html_url=observed.get("html_url"),
            private=observed.get("private"),
        )


def selected_names(args: argparse.Namespace) -> Iterable[str]:
    if args.all_sectors:
        return CANONICAL_SECTOR_REPOS
    if args.names:
        unknown = [n for n in args.names if n not in SECTORS]
        if unknown:
            raise SystemExit(f"Unknown canonical sectors: {', '.join(unknown)}")
        return tuple(dict.fromkeys(args.names))
    raise SystemExit("Specify --all-sectors or one or more --names")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create + bootstrap canonical KEDDEH Systems sector repositories")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--names", nargs="+")
    parser.add_argument("--all-sectors", action="store_true")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()
    names = tuple(selected_names(args))
    if args.dry_run:
        print(json.dumps({
            "mode": "DRY_RUN",
            "owner": args.owner,
            "private": args.private,
            "repositories": names,
            "bootstrap_files": list(GitHubRepoCreator.bootstrap_files(names[0])) if names else [],
        }, indent=2))
        return 0
    token = os.getenv(args.token_env, "")
    if not token:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": f"Missing environment credential: {args.token_env}",
            "owner": args.owner,
            "repositories": names,
            "next_transition": "SUPPLY_REPOSITORY_CREATION_AUTHORITY_AND_REEXECUTE",
        }, indent=2), file=sys.stderr)
        return 2
    creator = GitHubRepoCreator(token, args.owner)
    results = [creator.create_and_bootstrap(name, private=args.private) for name in names]
    print(json.dumps({
        "status": "COMPLETE",
        "owner": args.owner,
        "results": [asdict(result) for result in results],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
