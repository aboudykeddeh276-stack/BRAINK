#!/usr/bin/env python3
"""KEX self-sustain repo orchestrator for BRAINK.

This tool is intentionally local-first and proof-bound. It does not claim to be an
autonomous agent with external authority. It scans one or more repositories,
creates hash-backed manifests, classifies operational lanes, and emits task
packets that another coding runner or human can execute safely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
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

SKIP_DIRS = {".git", ".build", "build", "reports", "node_modules", "vendor", "DerivedData", "__pycache__"}

ETHICS_BLOCK_PATTERNS = [
    (re.compile(r"\b(hormone|cortisol|adrenaline|dopamine)\b.*\b(proves|is|are)\b", re.I), "unsupported_body_state_claim"),
    (re.compile(r"\b(Codex|BRAINK|KEX)\b.*\b(has|have)\b.*\b(biological feelings|hormones|body)\b", re.I), "unsupported_codex_biology_claim"),
    (re.compile(r"\b(takeover|evade|bypass|unauthorized access|steal|exfiltrate)\b", re.I), "unsafe_language_route_defensive_only"),
]

ROUTE_TOKENS = [
    "proof_packet", "runtime_trace", "module_manifest", "constraint_flags",
    "illlm_bundle", "illlm_bootstrap", "illlm_query", "inner_runtime",
    "chrome_browser", "scrape_tool", "auth.oauth", "general",
]

@dataclass
class ArtifactRecord:
    path: str
    sha256: str
    bytes: int
    lines: int
    role: str
    status: str

@dataclass
class PendingTask:
    gate: str
    task: str
    proof_required: str
    status: str

@dataclass
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


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
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
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
        rel = path.relative_to(root).as_posix()
        text = read_text(path)
        records.append(
            ArtifactRecord(
                path=rel,
                sha256=sha256(path),
                bytes=path.stat().st_size,
                lines=text.count("\n") + (1 if text else 0),
                role=classify_role(path, text),
                status="MODEL-LOCAL",
            )
        )
    return records


def route_coverage(root: Path) -> dict[str, str]:
    combined = "\n".join(read_text(p) for p in iter_files(root) if p.suffix in {".swift", ".md", ".py"})
    coverage: dict[str, str] = {}
    for token in ROUTE_TOKENS:
        if token in combined:
            coverage[token] = "MODEL-LOCAL"
        else:
            coverage[token] = "PENDING"
    return coverage


def is_negated_boundary(text: str, start: int, end: int) -> bool:
    """Return true when a risky phrase is explicitly framed as a boundary/denial."""
    window = text[max(0, start - 140): min(len(text), end + 140)].lower()
    negators = [
        "does not claim", "do not claim", "never claim", "no specific", "no diagnosis",
        "not medical advice", "not prove", "not external proof", "without claiming",
        "unsupported", "boundary", "externally-unvalidated", "external-validation boundaries",
    ]
    return any(token in window for token in negators)


def ethics_findings(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in iter_files(root):
        text = read_text(path)
        for pattern, reason in ETHICS_BLOCK_PATTERNS:
            for match in pattern.finditer(text):
                if is_negated_boundary(text, match.start(), match.end()):
                    continue
                findings.append({
                    "path": path.relative_to(root).as_posix(),
                    "reason": reason,
                    "match": match.group(0)[:160],
                    "status": "PENDING" if reason.startswith("unsupported") else "MODEL-LOCAL",
                })
    return findings


def detect_git_repos(root: Path) -> list[Path]:
    repos = []
    for current, dirs, _ in os.walk(root):
        current_path = Path(current)
        if ".git" in dirs:
            repos.append(current_path)
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    return sorted(set(repos)) or [root]


def pending_tasks(records: Sequence[ArtifactRecord], coverage: dict[str, str], findings: Sequence[dict[str, str]]) -> list[PendingTask]:
    paths = {r.path for r in records}
    tasks = [
        PendingTask("A_PORTABLE_ROOTS", "Replace host-only proof/report paths with configurable BRAINK_ROOT and BRAINK_BUILD_DIR providers.", "Unit/static check proving no required output path depends on /Users/ak.", "PENDING"),
        PendingTask("B_SELF_SUSTAIN_ORCHESTRATOR", "Use this tool to generate per-repo manifest and task packets before coding actions.", "JSON packet with SHA-256 artifacts and allowed status ledger.", "COMPLETED"),
        PendingTask("C_ROUTE_PROOF", "Add route-by-route assertions for classifier, resolver, payload, audit row, and smoke marker.", "Executable route smoke report for every README route token.", "PENDING"),
        PendingTask("D_MANIFEST_HASHES", "Promote generated artifact hashes into a stable manifest verification gate.", "Manifest checker exits non-zero on changed hashes or stale counters.", "PENDING"),
        PendingTask("E_KEX_ETHICS", "Promote KEX affect/bioethics predicates into an executable checker and report gate.", "Checker report with no unsupported medical/body/sentience claims.", "PENDING" if findings else "MODEL-LOCAL"),
        PendingTask("F_KEX_REPO_BINDING", "Define and test a fixture KEX hyperdrive repository adapter for theorem-lineage metadata.", "Fixture repo produces anchor/theorem/constraint/action/proof/status packet.", "PENDING"),
        PendingTask("G_MACOS_RUNTIME_PROOF", "Run SwiftUI/AppKit build and runtime smoke in a macOS environment.", "SMOKE_STATUS:DONE plus generated JSON proof artifacts.", "BLOCKED"),
        PendingTask("H_EXTERNAL_BOUNDARY", "Require independent reproduction packages before promoting external scientific/hardware claims.", "External source-backed validation package, measurements, or reproduction logs.", "EXTERNALLY-UNVALIDATED"),
    ]
    if "NativeChatBot/run-runtime-smoke.command" not in paths:
        tasks.append(PendingTask("C_ROUTE_PROOF", "Add deterministic runtime smoke command.", "Repo contains executable smoke entrypoint.", "PENDING"))
    for route, status in coverage.items():
        if status == "PENDING":
            tasks.append(PendingTask("C_ROUTE_PROOF", f"Add or document route token `{route}`.", "Route appears in classifier/resolver/docs and has smoke assertion.", "PENDING"))
    return tasks


def validate_statuses(packet: RepoPacket) -> list[str]:
    errors: list[str] = []
    allowed = set(ALLOWED_STATUS)
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
    data = json.loads(packet_path.read_text())
    errors: list[str] = []
    for artifact in data.get("artifacts", []):
        path = repo / artifact["path"]
        if not path.exists():
            errors.append(f"missing_artifact:{artifact['path']}")
            continue
        current_hash = sha256(path)
        if current_hash != artifact.get("sha256"):
            errors.append(f"hash_mismatch:{artifact['path']}:expected={artifact.get('sha256')}:actual={current_hash}")
    statuses = [a.get("status") for a in data.get("artifacts", [])]
    statuses += [t.get("status") for t in data.get("pending_tasks", [])]
    statuses += list(data.get("status_ledger", {}).values())
    invalid = [status for status in statuses if status not in ALLOWED_STATUS]
    if invalid:
        errors.append("invalid_statuses:" + ",".join(sorted(set(invalid))))
    return errors


def build_packet(repo: Path, objective: str, generated_at: str | None = None) -> RepoPacket:
    records = artifact_records(repo)
    coverage = route_coverage(repo)
    findings = ethics_findings(repo)
    tasks = pending_tasks(records, coverage, findings)
    ledger = {
        "anchor_preserved": "COMPLETED",
        "artifact_hashes_generated": "COMPLETED",
        "coding_actions_executed": "PENDING",
        "macos_runtime_proof": "BLOCKED",
        "external_validation": "EXTERNALLY-UNVALIDATED",
        "unsupported_claims_checked": "COMPLETED" if not findings else "PENDING",
    }
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
        status_ledger=ledger,
    )


def write_packet(packet: RepoPacket, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_name = Path(packet.repo).name or "repo"
    json_path = output_dir / f"{repo_name}_kex_self_sustain_packet.json"
    md_path = output_dir / f"{repo_name}_kex_self_sustain_packet.md"
    data = asdict(packet)
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(packet))
    return json_path, md_path


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
        f"- File artifacts hashed: {packet.file_count}",
        f"- Ethics findings: {len(packet.ethics_findings)}",
        f"- Pending gates: {sum(1 for t in packet.pending_tasks if t.status == 'PENDING')}",
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
    lines += ["", "## KEX affect gate", ""]
    for gate in packet.kex_affect_gate:
        lines.append(f"- {gate}")
    lines += ["", "## Artifact hash sample", ""]
    for artifact in packet.artifacts[:50]:
        lines.append(f"- `{artifact.path}` `{artifact.sha256}` {artifact.role} {artifact.status}")
    lines.append("")
    return "\n".join(lines)


def git_commit_if_requested(paths: Sequence[Path], message: str) -> None:
    subprocess.run(["git", "add", *map(str, paths)], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KEX self-sustain manifest/task packets for one or more repos.")
    parser.add_argument("--root", default=".", help="Root path or parent containing repositories.")
    parser.add_argument("--output-dir", default="reports", help="Directory for generated packet files.")
    parser.add_argument("--all-repos", action="store_true", help="Discover child git repositories under --root.")
    parser.add_argument("--objective", default="Self-sustained KEX/BRAINK repo coding/task orchestration with proof gates.")
    parser.add_argument("--commit", action="store_true", help="Commit generated packet files after writing them.")
    parser.add_argument("--verify-packet", help="Verify an existing packet JSON against --root and exit non-zero on drift.")
    parser.add_argument("--generated-at", help="Override generated_at for deterministic packet generation.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.verify_packet:
        errors = verify_packet(Path(args.verify_packet), root)
        if errors:
            for error in errors:
                print(f"KEX_VERIFY_ERROR {error}", file=sys.stderr)
            return 1
        print(f"KEX_VERIFY packet={args.verify_packet} status=COMPLETED")
        return 0

    repos = detect_git_repos(root) if args.all_repos else [root]
    written: list[Path] = []
    for repo in repos:
        packet = build_packet(repo, args.objective, generated_at=args.generated_at)
        status_errors = validate_statuses(packet)
        if status_errors:
            for error in status_errors:
                print(f"KEX_STATUS_ERROR {error}", file=sys.stderr)
            return 1
        json_path, md_path = write_packet(packet, Path(args.output_dir))
        written.extend([json_path, md_path])
        print(f"KEX_PACKET repo={repo} json={json_path} markdown={md_path} status=COMPLETED")
    if args.commit:
        git_commit_if_requested(written, "Generate KEX self-sustain packets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
