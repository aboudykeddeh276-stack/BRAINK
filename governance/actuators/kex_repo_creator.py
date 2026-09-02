#!/usr/bin/env python3
"""KEDDEH Systems GitHub Repository Creator Actuator.

Creates canonical sector repositories through the GitHub REST API and verifies
creation by reading each repository back. Credentials are supplied only through
GITHUB_TOKEN (or --token-env pointing at another environment variable).
"""
from __future__ import annotations

import argparse
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
CANONICAL_SECTOR_REPOS = (
    "KEX",
    "DOMAIN-AUTHORITY",
    "NETWORK-FABRIC",
    "CLOUD-INFRASTRUCTURE",
    "K-DRIVE",
    "IL-LLM",
    "WORKBOOK-OS",
    "CASEPATH",
    "CLAIMPATH",
    "WEB-FABRIC",
    "EDGE-IOT",
    "SECURITY-AUTHORITY",
    "AGENTS-ORCHESTRATION",
    "EVIDENCE-LEDGER",
)


class GitHubAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepoResult:
    name: str
    full_name: str
    status: str
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
                "User-Agent": "KEX-BRAINK-Repo-Creator/1.0",
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

    def create_repo(self, name: str, *, private: bool, description: str) -> RepoResult:
        existing = self.get_repo(name)
        if existing:
            return RepoResult(
                name=name,
                full_name=str(existing.get("full_name", f"{self.owner}/{name}")),
                status="EXISTS",
                html_url=existing.get("html_url"),
                private=existing.get("private"),
            )

        login = self.authenticated_login()
        payload = {
            "name": name,
            "description": description,
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

        status, _created = self._request("POST", path, payload)
        if status not in (201, 202):
            raise GitHubAPIError(f"Unexpected create status {status} for {name}")

        observed = self.get_repo(name)
        if not observed:
            raise GitHubAPIError(f"Repository {self.owner}/{name} was not observable after creation")

        return RepoResult(
            name=name,
            full_name=str(observed.get("full_name", f"{self.owner}/{name}")),
            status="CREATED_AND_READ_BACK",
            html_url=observed.get("html_url"),
            private=observed.get("private"),
        )


def selected_names(args: argparse.Namespace) -> Iterable[str]:
    if args.all_sectors:
        return CANONICAL_SECTOR_REPOS
    if args.names:
        return tuple(dict.fromkeys(args.names))
    raise SystemExit("Specify --all-sectors or one or more --names")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create canonical KEDDEH Systems GitHub repositories")
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
        }, indent=2))
        return 0

    token = os.getenv(args.token_env, "")
    if not token:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": f"Missing environment credential: {args.token_env}",
            "owner": args.owner,
            "repositories": names,
        }, indent=2), file=sys.stderr)
        return 2

    creator = GitHubRepoCreator(token, args.owner)
    results: list[RepoResult] = []
    for name in names:
        results.append(creator.create_repo(
            name,
            private=args.private,
            description=f"Canonical KEDDEH Systems sector repository: {name}",
        ))

    print(json.dumps({
        "status": "COMPLETE",
        "owner": args.owner,
        "results": [asdict(result) for result in results],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
