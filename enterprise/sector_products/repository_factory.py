from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json, subprocess


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    source_dir: str
    description: str
    visibility: str = "private"


def load_specs(register_path: str | Path, package_root: str | Path) -> list[RepositorySpec]:
    register = json.loads(Path(register_path).read_text())
    root = Path(package_root)
    specs = []
    for item in register["repositories"]:
        name = item["repository"]
        specs.append(RepositorySpec(
            name=name,
            source_dir=str(root / "repositories" / name),
            description=f"BRAINK sector product runtime: {name}",
        ))
    return specs


def create_with_gh(spec: RepositorySpec, owner: str, *, dry_run: bool = True):
    """Create and publish one standalone sector repo using an already-authenticated gh CLI."""
    src = Path(spec.source_dir).resolve()
    if not src.is_dir():
        return {"status": "REJECTED", "reason": "SOURCE_DIR_MISSING", "source_dir": str(src)}
    repo = f"{owner}/{spec.name}"
    cmd = ["gh", "repo", "create", repo, "--source", str(src), "--push", "--description", spec.description]
    cmd.append("--private" if spec.visibility == "private" else "--public")
    if dry_run:
        return {"status": "DRY_RUN", "repository": repo, "command": cmd}
    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return {"status": "CREATED" if cp.returncode == 0 else "FAILED", "repository": repo,
            "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}


def create_all(specs: Iterable[RepositorySpec], owner: str, *, dry_run: bool = True):
    return [create_with_gh(spec, owner, dry_run=dry_run) for spec in specs]
