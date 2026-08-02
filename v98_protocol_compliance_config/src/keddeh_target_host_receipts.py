#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence

LOCAL_PASS = "LOCAL_PASS"
LOCAL_FAIL = "LOCAL_FAIL"
TARGET_HOST_REQUIRED = "TARGET_HOST_REQUIRED"
SERVICE_LABEL = "com.keddeh.service-spine"
REQUIRED_CHECK_IDS = {
    "runner_context",
    "host_os",
    "host_arch",
    "launchd_service",
    "iostat_sample",
}


@dataclass(frozen=True)
class CommandResult:
    command: List[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class TargetHostCheck:
    check_id: str
    status: str
    executed: bool
    command: List[str]
    returncode: int | None
    detail: str
    metrics: Dict[str, Any]


CommandRunner = Callable[[Sequence[str]], CommandResult]


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_ledger(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bounded_text(value: str, limit: int = 4096) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[:limit] + "...<truncated>"


def run_command(command: Sequence[str]) -> CommandResult:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
        return CommandResult(
            command=list(command),
            returncode=result.returncode,
            stdout=bounded_text(result.stdout),
            stderr=bounded_text(result.stderr),
        )
    except Exception as exc:
        return CommandResult(list(command), 127, "", f"{type(exc).__name__}:{exc}")


def parse_iostat_metrics(stdout: str) -> Dict[str, Any]:
    numeric_lines: List[List[float]] = []
    for raw_line in stdout.splitlines():
        values = re.findall(r"(?<![A-Za-z])[+-]?(?:\d+(?:\.\d+)?|\.\d+)", raw_line)
        if len(values) >= 4:
            numeric_lines.append([float(value) for value in values])
    return {
        "numeric_sample_lines": len(numeric_lines),
        "last_sample": numeric_lines[-1] if numeric_lines else [],
    }


def collect_checks(
    *,
    command_runner: CommandRunner = run_command,
    environ: Mapping[str, str] | None = None,
    system: str | None = None,
    machine: str | None = None,
    uid: int | None = None,
) -> List[TargetHostCheck]:
    env = dict(os.environ if environ is None else environ)
    host_system = platform.system() if system is None else system
    host_machine = platform.machine() if machine is None else machine
    host_uid = os.getuid() if uid is None else uid

    github_actions = env.get("GITHUB_ACTIONS", "").lower() == "true"
    self_hosted = env.get("RUNNER_ENVIRONMENT", "").lower() == "self-hosted"
    runner_os = env.get("RUNNER_OS", "")
    runner_arch = env.get("RUNNER_ARCH", "")
    runner_context_passed = (
        github_actions
        and self_hosted
        and runner_os.lower() == "macos"
        and runner_arch.lower() in {"arm64", "aarch64"}
    )
    checks = [
        TargetHostCheck(
            check_id="runner_context",
            status=LOCAL_PASS if runner_context_passed else TARGET_HOST_REQUIRED,
            executed=github_actions,
            command=[],
            returncode=None,
            detail=(
                "GitHub Actions scheduled this job onto a self-hosted macOS ARM64 runner. "
                "The custom KEDDEH-M3 label remains corroborated by the workflow runs-on constraint."
                if runner_context_passed
                else "A self-hosted GitHub Actions context with macOS and ARM64 runner metadata is required."
            ),
            metrics={
                "github_actions": github_actions,
                "runner_environment": env.get("RUNNER_ENVIRONMENT", ""),
                "runner_os": runner_os,
                "runner_arch": runner_arch,
                "runner_name": env.get("RUNNER_NAME", ""),
                "github_run_id": env.get("GITHUB_RUN_ID", ""),
                "github_sha": env.get("GITHUB_SHA", ""),
            },
        ),
        TargetHostCheck(
            check_id="host_os",
            status=LOCAL_PASS if host_system == "Darwin" else TARGET_HOST_REQUIRED,
            executed=True,
            command=[],
            returncode=None,
            detail=f"platform.system()={host_system}",
            metrics={"system": host_system},
        ),
        TargetHostCheck(
            check_id="host_arch",
            status=LOCAL_PASS if host_machine.lower() in {"arm64", "aarch64"} else TARGET_HOST_REQUIRED,
            executed=True,
            command=[],
            returncode=None,
            detail=f"platform.machine()={host_machine}",
            metrics={"machine": host_machine},
        ),
    ]

    if host_system != "Darwin":
        checks.extend(
            [
                TargetHostCheck(
                    "launchd_service",
                    TARGET_HOST_REQUIRED,
                    False,
                    [],
                    None,
                    "launchd service readback requires macOS.",
                    {},
                ),
                TargetHostCheck(
                    "iostat_sample",
                    TARGET_HOST_REQUIRED,
                    False,
                    [],
                    None,
                    "macOS iostat sampling requires the target workstation.",
                    {},
                ),
            ]
        )
        return checks

    launchctl_command = ["/bin/launchctl", "print", f"gui/{host_uid}/{SERVICE_LABEL}"]
    launchctl_result = command_runner(launchctl_command)
    launchctl_text = f"{launchctl_result.stdout}\n{launchctl_result.stderr}"
    launchctl_passed = launchctl_result.returncode == 0 and SERVICE_LABEL in launchctl_text
    checks.append(
        TargetHostCheck(
            check_id="launchd_service",
            status=LOCAL_PASS if launchctl_passed else LOCAL_FAIL,
            executed=True,
            command=launchctl_result.command,
            returncode=launchctl_result.returncode,
            detail=(
                "LaunchAgent is loaded and readable through launchctl."
                if launchctl_passed
                else "LaunchAgent readback failed or returned the wrong service label."
            ),
            metrics={
                "service_label": SERVICE_LABEL,
                "stdout": launchctl_result.stdout,
                "stderr": launchctl_result.stderr,
            },
        )
    )

    iostat_command = ["/usr/sbin/iostat", "-d", "-c", "2", "-w", "1"]
    iostat_result = command_runner(iostat_command)
    iostat_metrics = parse_iostat_metrics(iostat_result.stdout)
    iostat_passed = iostat_result.returncode == 0 and iostat_metrics["numeric_sample_lines"] > 0
    checks.append(
        TargetHostCheck(
            check_id="iostat_sample",
            status=LOCAL_PASS if iostat_passed else LOCAL_FAIL,
            executed=True,
            command=iostat_result.command,
            returncode=iostat_result.returncode,
            detail=(
                "iostat returned at least one parseable numeric device sample."
                if iostat_passed
                else "iostat did not return a successful parseable device sample."
            ),
            metrics={
                **iostat_metrics,
                "stdout": iostat_result.stdout,
                "stderr": iostat_result.stderr,
            },
        )
    )
    return checks


def run_target_host_receipts(
    root: Path,
    *,
    emit_receipt: bool = False,
    command_runner: CommandRunner = run_command,
    environ: Mapping[str, str] | None = None,
    system: str | None = None,
    machine: str | None = None,
    uid: int | None = None,
) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    started = time.time()
    checks = collect_checks(
        command_runner=command_runner,
        environ=environ,
        system=system,
        machine=machine,
        uid=uid,
    )
    check_payload = [asdict(check) for check in checks]
    classification_counts: Dict[str, int] = {}
    for check in checks:
        classification_counts[check.status] = classification_counts.get(check.status, 0) + 1

    required_checks = [check for check in checks if check.check_id in REQUIRED_CHECK_IDS]
    all_required_checks_passed = all(check.status == LOCAL_PASS for check in required_checks)
    pre_receipt = {
        "version": "V98",
        "receipt_type": "target_host_execution_receipt",
        "checks": check_payload,
        "classification_counts": classification_counts,
        "required_check_ids": sorted(REQUIRED_CHECK_IDS),
        "all_required_checks_passed": all_required_checks_passed,
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    evidence_path = root / "evidence" / "target_host_receipts.json"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_path = root / "runtime_volume" / "outbox" / "target_host" / f"{receipt_hash}.handoff.json"

    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_TARGET_HOST_RECEIPT_SERVICE",
        "payload_path": str(evidence_path),
        "receipt_path": str(ledger_path),
        "next_target": "v98_acceptance_harness",
        "status": "LOCAL_PASS" if all_required_checks_passed else "FAILED_CLOSED_OR_TARGET_HOST_REQUIRED",
        "created_at": started,
    }
    write_json(outbox_path, handoff)
    append_ledger(
        ledger_path,
        {
            "type": "target_host_execution_receipt",
            "entry_hash": receipt_hash,
            "payload": pre_receipt,
            "outbox_manifest": str(outbox_path),
        },
    )
    ledger_readback = any(
        entry.get("type") == "target_host_execution_receipt" and entry.get("entry_hash") == receipt_hash
        for entry in read_ledger(ledger_path)
    )
    final = {
        **pre_receipt,
        "receipt_hash": receipt_hash,
        "ledger_path": str(ledger_path),
        "ledger_readback": ledger_readback,
        "outbox_manifest": str(outbox_path),
        "hash_used_as_functional_proof": False,
        "telemetry_used_as_functional_proof": False,
        "manifest_used_as_functional_proof": False,
    }
    if emit_receipt:
        write_json(evidence_path, final)
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args(argv)
    result = run_target_host_receipts(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ledger_readback"]:
        return 1
    if args.require_all and not result["all_required_checks_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
