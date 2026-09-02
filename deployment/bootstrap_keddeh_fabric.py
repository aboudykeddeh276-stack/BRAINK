from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CANONICAL = "https://github.com/aboudykeddeh276-stack/BRAINK.git"
MANIFEST = "deployment/KEDDEH_SYSTEMS_RUNTIME_ACTIVE_R1.json"


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def hydrate(target: Path, *, refresh: bool = True) -> dict:
    target = target.resolve()
    if not (target / ".git").exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--depth", "1", CANONICAL, str(target))
    elif refresh:
        run("git", "fetch", "origin", "main", cwd=target)
        run("git", "checkout", "main", cwd=target)
        run("git", "reset", "--hard", "origin/main", cwd=target)

    manifest_path = target / MANIFEST
    manifest = json.loads(manifest_path.read_text("utf-8"))
    raw = manifest_path.read_bytes()
    receipt = {
        "status": "HYDRATED",
        "canonical": CANONICAL,
        "target": str(target),
        "manifest": MANIFEST,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "runtime_id": manifest["runtime_id"],
        "runtime_state": manifest["runtime_state"],
        "external_host_binding": manifest["external_host_binding"],
    }
    state_dir = Path.cwd() / ".braink"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "keddeh_fabric_runtime.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=".braink/canonical-BRAINK")
    ap.add_argument("--no-refresh", action="store_true")
    ns = ap.parse_args()
    print(json.dumps(hydrate(Path(ns.target), refresh=not ns.no_refresh), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
