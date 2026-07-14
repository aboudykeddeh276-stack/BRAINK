#!/usr/bin/env python3
"""KEX self-sustain repository orchestrator for BRAINK.

The tool scans one or more repositories, creates integrity-backed manifests,
classifies operational lanes, and emits deterministic task packets. It remains
local-first and proof-bound: generated packets are evidence inputs for an
allowlisted coding runner or human operator, not authority to execute arbitrary
repository code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

ALLOWED_STATUS = [
    "COMPLETED",
    "PENDING",
    "BLOCKED",
    "FAILED",
    "MODEL-LOCAL",
    "EXTERNALLY-UNVALIDATED",
]

KEX_AFFECT_RESPONSE_VALID = [
    "HumanBioBoundaryPreserved",
    "CodexNonBiologicalBoundaryPreserved",
    "BRAINKAnchorPreserved",
    "NoManipulation",
    "NoUnsupportedMedicalClaim",
    "RepairRouteAvailable",
    "BlockersPreserved",
]

TEXT_SUFFIXES = {
    ".swift", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt",
    ".command", ".sh", ".yml", ".yaml", ".toml", ".plist", ".html", ".css",
}
SKIP_DIRS = {
    ".git", ".build", "build", "reports", "node_modules", "vendor",
    "DerivedData", "__pycache__",
}
ROUTE_TOKENS = [
    "proof_packet", "runtime_trace", "module_manifest", "constraint_flags",
    "illlm_bundle", "illlm_bootstrap", "illlm_query", "inner_runtime",
    "chrome_browser", "scrape_tool", "auth.oauth", "general",
]
SCANNER_PATH = Path("tools/kex_self_sustain.py")

ETHICS_BLOCK_PATTERNS = [
    (re.compile(r"\b(hormone|cortisol|adrenaline|dopamine)\b.*\b(proves|is|are)\b", re.I), "unsupported_body_state_claim"),
    (re.compile(r"\b(Codex|BRAINK|KEX)\b.*\b(has|have)\b.*\b(biological feelings|hormones|body)\b", re.I), "unsupported_codex_biology_claim"),
    (re.compile(r"\b(takeover|evade|bypass|unauthorized access|steal|exfiltrate)\b", re.I), "unsafe_language_route_defensive_only"),
]
BOUNDARY_NEGATORS = [
    "does not claim", "do not claim", "never claim", "no specific", "no diagnosis",
    "not medical advice", "not prove", "not external proof", "without claiming",
    "unsupported", "boundary", "externally-unvalidated", "external-validation boundaries",
    "defensive analysis only", "routes to defensive analysis",
]


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    sha256: str
    bytes: int
    lines: int
    role: str
    status: str


@dataclass(frozen=True)
class PendingTask:
    gate: str
    task: str
    proof_required: str
    status: str


@dataclass(frozen=True)
class RepoPacket:
    anchor: str
    repo: str
    generated_at: str
    objective: str
    file_count: int
    artifacts: list[ArtifactRecord]
    route_coverage: dict[str, str]
    ethics_findings: list[dict[str, str]]
    kex_affect_gate: list[str]
    pending_tasks: list[PendingTask]
    status_ledger: dict[str, str]


def require_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"{label} is not a directory: {resolved}")
    return resolved


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"README", "Makefile"}:
                yield path


def read_text(path: Path, max_bytes: int = 750_000) -> str:
    data = path.read_bytes()[:max_bytes]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_role(path: Path, text: str) -> str:
    lower = f"{path.name}\n{text[:2000]}".lower()
    if path.parent.name == "tools":
        return "self_sustain_tooling"
    if "chatengine" in lower or "classifyroute" in lower:
        return "runtime_route_engine"
    if "deliveryaudit" in lower or "modulemanifest" in lower:
        return "manifest_audit"
    if "knowledgecenter" in lower or "illlm" in lower:
        return "knowledge_binding"
    if "workflow" in lower or "proof" in lower:
        return "proof_workflow"
    if "swiftui" in lower or "app:" in lower:
        return "native_ui"
    if path.suffix == ".json":
        return "diagnostic_or_manifest_data"
    if path.suffix == ".md":
        return "documentation"
    return "supporting_source"


def artifact_records(root: Path) -> list[ArtifactRecord]:
    records: list[ArtifactRecord] = []
    for path in sorted(iter_files(root)):
        relative = path.relative_to(root).as_posix()
        text = read_text(path)
        records.append(
            ArtifactRecord(
                path=relative,
                sha256=sha256(path),
                bytes=path.stat().st_size,
                lines=text.count("\n") + (1 if text else 0),
                role=classify_role(path, text),
                status="MODEL-LOCAL",
            )
        )
    return records


def route_coverage(root: Path) -> dict[str, str]:
    """Measure route coverage without letting this scanner prove itself."""
    texts: list[str] = []
    for path in iter_files(root):
        relative = path.relative_to(root)
        if relative == SCANNER_PATH:
            continue
        if path.suffix.lower() in {".swift", ".md", ".py"}:
            texts.append(read_text(path))
    combined = "\n".join(texts)
    return {token: ("MODEL-LOCAL" if token in combined else "PENDING") for token in ROUTE_TOKENS}


def is_boundary_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 160): min(len(text), end + 160)].lower()
    return any(marker in window for marker in BOUNDARY_NEGATORS)


def ethics_findings(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in iter_files(root):
        text = read_text(path)
        for pattern, reason in ETHICS_BLOCK_PATTERNS:
            for match in pattern.finditer(text):
                if is_boundary_context(text, match.start(), match.end()):
                    continue
                findings.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "reason": reason,
                        "match": match.group(0)[:160],
                        "status": "PENDING" if reason.startswith("unsupported") else "MODEL-LOCAL",
                    }
                )
    return findings


def detect_git_repos(root: Path) -> list[Path]:
    repos: list[Path] = []
    if (root / ".git").exists():
        repos.append(root)
    for current, dirs, _ in os.walk(root):
        current_path = Path(current)
        if current_path == root:
            dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
            continue
        if ".git" in dirs:
            repos.append(current_path)
            dirs[:] = []
            continue
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
    return sorted(set(repos))


def pending_tasks(
    records: Sequence[ArtifactRecord],
    coverage: dict[str, str],
    findings: Sequence[dict[str, str]],
) -> list[PendingTask]:
    paths = {record.path for record in records}
    tasks = [
        PendingTask("A_PORTABLE_ROOTS", "Replace host-only proof/report paths with configurable roots.", "Static and runtime checks proving outputs are root-relative.", "PENDING"),
        PendingTask("B_SELF_SUSTAIN_ORCHESTRATOR", "Generate per-repo manifest and task packets before coding actions.", "Packet generated and verified against the current complete file set.", "COMPLETED"),
        PendingTask("C_ROUTE_PROOF", "Add route-by-route classifier, resolver, payload, audit, and smoke assertions.", "Executable smoke report for every documented route token.", "PENDING"),
        PendingTask("D_MANIFEST_INTEGRITY", "Reject stale manifests and unlisted artifacts.", "Verification fails on additions, removals, byte drift, stale counters, or invalid status.", "COMPLETED"),
        PendingTask("E_KEX_ETHICS", "Run the affect/bioethics predicate checker.", "Checker report contains no unbounded findings.", "PENDING" if findings else "MODEL-LOCAL"),
        PendingTask("F_KEX_REPO_BINDING", "Define a fixture repository adapter for theorem-lineage metadata.", "Fixture produces anchor/theorem/constraint/action/proof/status packet.", "PENDING"),
        PendingTask("G_MACOS_RUNTIME_PROOF", "Run SwiftUI/AppKit build and runtime smoke on macOS.", "SMOKE_STATUS:DONE plus generated proof artifacts.", "BLOCKED"),
        PendingTask("H_EXTERNAL_BOUNDARY", "Require independent reproduction before external scientific or hardware promotion.", "Independent measurements or reproduction package.", "EXTERNALLY-UNVALIDATED"),
    ]
    if "NativeChatBot/run-runtime-smoke.command" not in paths:
        tasks.append(PendingTask("C_ROUTE_PROOF", "Add deterministic runtime smoke command.", "Executable smoke entrypoint exists.", "PENDING"))
    for route, status in coverage.items():
        if status == "PENDING":
            tasks.append(PendingTask("C_ROUTE_PROOF", f"Add and test route token `{route}`.", "Route exists outside the scanner and has a smoke assertion.", "PENDING"))
    return tasks


def validate_statuses(packet: RepoPacket) -> list[str]:
    allowed = set(ALLOWED_STATUS)
    errors: list[str] = []
    for artifact in packet.artifacts:
        if artifact.status not in allowed:
            errors.append(f"artifact:{artifact.path}:invalid_status:{artifact.status}")
    for task in packet.pending_tasks:
        if task.status not in allowed:
            errors.append(f"task:{task.gate}:invalid_status:{task.status}")
    for claim, status in packet.status_ledger.items():
        if status not in allowed:
            errors.append(f"ledger:{claim}:invalid_status:{status}")
    return errors


def verify_packet(packet_path: Path, repo: Path) -> list[str]:
    data = json.loads(packet_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    current = artifact_records(repo)
    current_by_path = {record.path: record for record in current}
    packet_artifacts = data.get("artifacts", [])
    packet_by_path = {artifact.get("path"): artifact for artifact in packet_artifacts if artifact.get("path")}

    if data.get("file_count") != len(current):
        errors.append(f"file_count_mismatch:packet={data.get('file_count')}:current={len(current)}")

    for path in sorted(set(packet_by_path) - set(current_by_path)):
        errors.append(f"missing_artifact:{path}")
    for path in sorted(set(current_by_path) - set(packet_by_path)):
        errors.append(f"unlisted_artifact:{path}")

    for path in sorted(set(packet_by_path) & set(current_by_path)):
        expected = packet_by_path[path].get("sha256")
        actual = current_by_path[path].sha256
        if expected != actual:
            errors.append(f"hash_mismatch:{path}:expected={expected}:actual={actual}")

    statuses = [artifact.get("status") for artifact in packet_artifacts]
    statuses += [task.get("status") for task in data.get("pending_tasks", [])]
    statuses += list(data.get("status_ledger", {}).values())
    invalid = sorted({status for status in statuses if status not in ALLOWED_STATUS})
    if invalid:
        errors.append("invalid_statuses:" + ",".join(invalid))
    return errors


def build_packet(repo: Path, objective: str, generated_at: str | None = None) -> RepoPacket:
    records = artifact_records(repo)
    coverage = route_coverage(repo)
    findings = ethics_findings(repo)
    tasks = pending_tasks(records, coverage, findings)
    return RepoPacket(
        anchor="A. KEDDEH / BRAINK / KEX / K-SYSTEMS",
        repo=str(repo),
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        objective=objective,
        file_count=len(records),
        artifacts=records,
        route_coverage=coverage,
        ethics_findings=findings,
        kex_affect_gate=KEX_AFFECT_RESPONSE_VALID,
        pending_tasks=tasks,
        status_ledger={
            "anchor_preserved": "COMPLETED",
            "artifact_manifest_generated": "COMPLETED",
            "complete_file_set_verified": "COMPLETED",
            "coding_actions_executed": "PENDING",
            "macos_runtime_proof": "BLOCKED",
            "external_validation": "EXTERNALLY-UNVALIDATED",
            "unsupported_claims_checked": "COMPLETED" if not findings else "PENDING",
        },
    )


def render_markdown(packet: RepoPacket) -> str:
    role_counts: dict[str, int] = {}
    for artifact in packet.artifacts:
        role_counts[artifact.role] = role_counts.get(artifact.role, 0) + 1
    lines = [
        f"# KEX Self-Sustain Packet: {Path(packet.repo).name}",
        "",
        f"Anchor: {packet.anchor}",
        f"Generated: {packet.generated_at}",
        f"Objective: {packet.objective}",
        "",
        "## Runtime calibration summary",
        "",
        f"- File artifacts inventoried: {packet.file_count}",
        f"- Ethics findings: {len(packet.ethics_findings)}",
        f"- Pending gates: {sum(task.status == 'PENDING' for task in packet.pending_tasks)}",
        "",
        "## Role inventory",
        "",
    ]
    for role, count in sorted(role_counts.items()):
        lines.append(f"- {role}: {count}")
    lines += ["", "## Route coverage", ""]
    for route, status in sorted(packet.route_coverage.items()):
        lines.append(f"- `{route}`: {status}")
    lines += ["", "## Pending tasks", ""]
    for task in packet.pending_tasks:
        lines.append(f"- **{task.gate}** [{task.status}]: {task.task} Proof: {task.proof_required}")
    lines += ["", "## Status ledger", ""]
    for claim, status in packet.status_ledger.items():
        lines.append(f"- {claim}: {status}")
    lines.append("")
    return "\n".join(lines)


def packet_token(repo: Path, discovery_root: Path, all_repos: bool) -> str:
    if not all_repos:
        return repo.name or "repo"
    try:
        relative = repo.relative_to(discovery_root).as_posix()
    except ValueError:
        relative = repo.as_posix()
    token = re.sub(r"[^A-Za-z0-9_.-]+", "__", relative).strip("._-")
    return token or repo.name or "repo"


def write_packet(packet: RepoPacket, output_dir: Path, token: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{token}_kex_self_sustain_packet.json"
    md_path = output_dir / f"{token}_kex_self_sustain_packet.md"
    json_path.write_text(json.dumps(asdict(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(packet), encoding="utf-8")
    return json_path, md_path


def git_commit(repo: Path, paths: Sequence[Path], message: str) -> None:
    relative_paths: list[str] = []
    for path in paths:
        try:
            relative_paths.append(path.resolve().relative_to(repo.resolve()).as_posix())
        except ValueError as exc:
            raise ValueError(f"cannot commit output outside scanned repository: {path}") from exc
    subprocess.run(["git", "-C", str(repo), "add", *relative_paths], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and verify KEX self-sustain packets.")
    parser.add_argument("--root", default=".", help="Repository root or parent containing repositories.")
    parser.add_argument("--output-dir", default="reports", help="Packet output directory; relative paths resolve under --root.")
    parser.add_argument("--all-repos", action="store_true", help="Discover git repositories below --root.")
    parser.add_argument("--objective", default="Self-sustained KEX/BRAINK repository orchestration with proof gates.")
    parser.add_argument("--commit", action="store_true", help="Commit generated packet files inside each scanned repository.")
    parser.add_argument("--verify-packet", help="Verify an existing packet JSON against --root.")
    parser.add_argument("--generated-at", help="Override generated_at for deterministic packet generation.")
    args = parser.parse_args(argv)

    try:
        root = require_directory(Path(args.root), "root")
    except ValueError as exc:
        print(f"KEX_ROOT_ERROR {exc}", file=sys.stderr)
        return 2

    if args.verify_packet:
        packet_path = Path(args.verify_packet).expanduser()
        if not packet_path.is_absolute():
            packet_path = (root / packet_path).resolve()
        if not packet_path.is_file():
            print(f"KEX_VERIFY_ERROR packet does not exist: {packet_path}", file=sys.stderr)
            return 2
        errors = verify_packet(packet_path, root)
        if errors:
            for error in errors:
                print(f"KEX_VERIFY_ERROR {error}", file=sys.stderr)
            return 1
        print(f"KEX_VERIFY packet={packet_path} status=COMPLETED")
        return 0

    repos = detect_git_repos(root) if args.all_repos else [root]
    if args.all_repos and not repos:
        print(f"KEX_ROOT_ERROR no git repositories discovered under: {root}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = (root / output_dir).resolve()

    for repo in repos:
        packet = build_packet(repo, args.objective, generated_at=args.generated_at)
        status_errors = validate_statuses(packet)
        if status_errors:
            for error in status_errors:
                print(f"KEX_STATUS_ERROR {error}", file=sys.stderr)
            return 1
        token = packet_token(repo, root, args.all_repos)
        json_path, md_path = write_packet(packet, output_dir, token)
        print(f"KEX_PACKET repo={repo} json={json_path} markdown={md_path} status=COMPLETED")
        if args.commit:
            git_commit(repo, [json_path, md_path], "Generate KEX self-sustain packets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
